#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <thread>

#include "utils/interpolation.hpp"
#include "warp2d/warp2d.hpp"

std::vector<Centroid::Peak> Warp2D::peaks_in_rt_range(
    const std::vector<Centroid::Peak>& source_peaks, double time_start,
    double time_end) {
    std::vector<Centroid::Peak> ret;
    ret.reserve(source_peaks.size());
    size_t i = 0;
    for (const auto& peak : source_peaks) {
        if (peak.local_max_rt >= time_start && peak.local_max_rt < time_end) {
            ret.push_back(peak);
            ++i;
        }
        // TODO(alex): Should we use rt or rt_centroid?
    }
    ret.resize(i);
    return ret;
}

double Warp2D::peak_overlap(const Centroid::Peak& peak_a,
                            const Centroid::Peak& peak_b) {
    // TODO(alex): Use rt/mz/height or rt_centroid/mz_centroid/height_centroid?

    // Early return if the peaks do not intersect in the +/-3 * sigma_mz/rt
    {
        double min_rt_a = peak_a.local_max_rt - 3 * peak_a.raw_roi_sigma_rt;
        double max_rt_a = peak_a.local_max_rt + 3 * peak_a.raw_roi_sigma_rt;
        double min_mz_a = peak_a.local_max_mz - 3 * peak_a.raw_roi_sigma_mz;
        double max_mz_a = peak_a.local_max_mz + 3 * peak_a.raw_roi_sigma_mz;
        double min_rt_b = peak_b.local_max_rt - 3 * peak_b.raw_roi_sigma_rt;
        double max_rt_b = peak_b.local_max_rt + 3 * peak_b.raw_roi_sigma_rt;
        double min_mz_b = peak_b.local_max_mz - 3 * peak_b.raw_roi_sigma_mz;
        double max_mz_b = peak_b.local_max_mz + 3 * peak_b.raw_roi_sigma_mz;

        if (max_rt_a < min_rt_b || max_rt_b < min_rt_a || max_mz_a < min_mz_b ||
            max_mz_b < min_mz_a) {
            return 0;
        }
    }

    // Calculate the gaussian contribution of the overlap between two points in
    // one dimension.
    auto gaussian_contribution = [](double x_a, double x_b, double sigma_a,
                                    double sigma_b) -> double {
        double var_a = std::pow(sigma_a, 2);
        double var_b = std::pow(sigma_b, 2);

        double a = (var_a + var_b) / (var_a * var_b) *
                   std::pow((x_a * var_b + x_b * var_a) / (var_a + var_b), 2);
        double b = (x_a * x_a) / var_a + (x_b * x_b) / var_b;

        return std::exp(0.5 * (a - b)) / std::sqrt(var_a + var_b);
    };

    auto rt_contrib =
        gaussian_contribution(peak_a.local_max_rt, peak_b.local_max_rt,
                              peak_a.raw_roi_sigma_rt, peak_b.raw_roi_sigma_rt);
    auto mz_contrib =
        gaussian_contribution(peak_a.local_max_mz, peak_b.local_max_mz,
                              peak_a.raw_roi_sigma_mz, peak_b.raw_roi_sigma_mz);

    return rt_contrib * mz_contrib * peak_a.local_max_height *
           peak_b.local_max_height;
}

double Warp2D::similarity_2D(const std::vector<Centroid::Peak>& set_a,
                             const std::vector<Centroid::Peak>& set_b) {
    double cumulative_similarity = 0;
    for (const auto& peak_a : set_a) {
        for (const auto& peak_b : set_b) {
            cumulative_similarity += Warp2D::peak_overlap(peak_a, peak_b);
        }
    }
    return cumulative_similarity;
}

std::vector<Centroid::Peak> Warp2D::filter_peaks(
    std::vector<Centroid::Peak>& peaks, size_t n_peaks_max) {
    std::vector<Centroid::Peak> filtered_peaks;
    size_t n_peaks = n_peaks_max < peaks.size() ? n_peaks_max : peaks.size();
    if (n_peaks == 0) {
        return filtered_peaks;
    }
    filtered_peaks.reserve(n_peaks);
    auto sort_by_height = [](const Centroid::Peak& p1,
                             const Centroid::Peak& p2) -> bool {
        return (p1.local_max_height > p2.local_max_height);
    };
    std::sort(peaks.begin(), peaks.end(), sort_by_height);
    for (size_t i = 0; i < n_peaks; ++i) {
        auto peak = peaks[i];
        filtered_peaks.push_back(peak);
    }
    return filtered_peaks;
}

std::vector<Warp2D::Level> Warp2D::initialize_levels(int64_t N, int64_t m,
                                                     int64_t t, int64_t nP) {
    std::vector<Level> levels(N + 1);
    for (int64_t i = 0; i < N; ++i) {
        int64_t start = std::max((i * (m - t)), (nP - (N - i) * (m + t)));
        int64_t end = std::min((i * (m + t)), (nP - (N - i) * (m - t)));
        int64_t length = end - start + 1;
        levels[i].start = start;
        levels[i].end = end;
        levels[i].nodes = std::vector<Node>(length);
        for (int64_t j = 0; j < length; ++j) {
            levels[i].nodes[j].f = -std::numeric_limits<double>::infinity();
            levels[i].nodes[j].u = 0;
        }
    }
    levels[N].start = nP;
    levels[N].end = nP;
    levels[N].nodes.push_back({0.0, 0});

    // Calculate potential warpings on each level.
    for (int64_t k = 0; k < N; ++k) {
        auto& current_level = levels[k];
        const auto& next_level = levels[k + 1];

        for (int64_t i = 0; i < (int64_t)current_level.nodes.size(); ++i) {
            int64_t src_start = current_level.start + i;

            // The next node for the next level is subject to the following
            // constrains:
            //
            // x_{i + 1} = x_{i} + m + u, where u <- [-t, t]
            //
            int64_t x_end_min = std::max(src_start + m - t, next_level.start);
            int64_t x_end_max = std::min(src_start + m + t, next_level.end);
            int64_t j_min = x_end_min - next_level.start;
            int64_t j_max = x_end_max - next_level.start;
            for (int64_t j = j_min; j <= j_max; ++j) {
                int64_t src_end = next_level.start + j;
                levels[k].potential_warpings.push_back(
                    {i, j, src_start, src_end, 0});
            }
        }
    }
    return levels;
}

std::vector<Centroid::Peak> Warp2D::warp_peaks(
    const std::vector<Centroid::Peak>& source_peaks, double source_rt_start,
    double source_rt_end, double ref_rt_start, double ref_rt_end) {
    auto warped_peaks =
        Warp2D::peaks_in_rt_range(source_peaks, source_rt_start, source_rt_end);

    for (auto& peak : warped_peaks) {
        double x = (peak.local_max_rt - source_rt_start) /
                   (source_rt_end - source_rt_start);
        peak.local_max_rt = Interpolation::lerp(ref_rt_start, ref_rt_end, x);
    }
    return warped_peaks;
}

void Warp2D::compute_warped_similarities(
    Warp2D::Level& level, double rt_start, double rt_end, double rt_min,
    double delta_rt, const std::vector<Centroid::Peak>& target_peaks,
    const std::vector<Centroid::Peak>& source_peaks) {
    auto target_peaks_segment =
        Warp2D::peaks_in_rt_range(target_peaks, rt_start, rt_end);

    for (auto& warping : level.potential_warpings) {
        int64_t src_start = warping.src_start;
        int64_t src_end = warping.src_end;

        double sample_rt_start = rt_min + warping.src_start * delta_rt;
        double sample_rt_width = (src_end - src_start) * delta_rt;
        double sample_rt_end = sample_rt_start + sample_rt_width;

        auto source_peaks_warped = Warp2D::warp_peaks(
            source_peaks, sample_rt_start, sample_rt_end, rt_start, rt_end);

        double similarity =
            Warp2D::similarity_2D(target_peaks_segment, source_peaks_warped);
        warping.warped_similarity = similarity;
    }
};

std::vector<int64_t> Warp2D::find_optimal_warping(std::vector<Level>& levels) {
    int64_t N = levels.size() - 1;

    // Perform dynamic programming to update the cumulative similarity and the
    // optimal predecessor.
    for (int64_t k = N - 1; k >= 0; --k) {
        auto& current_level = levels[k];
        const auto& next_level = levels[k + 1];
        for (const auto& warping : current_level.potential_warpings) {
            auto& node_i = current_level.nodes[warping.i];
            const auto& node_j = next_level.nodes[warping.j];
            double f_sum = node_j.f + warping.warped_similarity;
            if (f_sum > node_i.f) {
                node_i.f = f_sum;
                node_i.u = warping.j;
            }
        }
    }

    // Walk forward nodes to find optimal warping path.
    std::vector<int64_t> warp_by;
    warp_by.reserve(N + 1);
    warp_by.push_back(0);
    for (int64_t i = 0; i < N; ++i) {
        auto u = levels[i].nodes[warp_by[i]].u;
        warp_by.push_back(u);
    }
    return warp_by;
}