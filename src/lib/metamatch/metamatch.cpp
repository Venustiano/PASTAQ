#include <algorithm>
#include <sstream>

#include "metamatch/metamatch.hpp"

void calculate_cluster_pos(double& cluster_mz, double& cluster_rt,
                           std::vector<MetaMatch::Peak>& peaks,
                           std::vector<size_t>& metapeak_indexes) {
    double x_sum = 0;
    double y_sum = 0;
    double height_sum = 0;
    for (const auto& index : metapeak_indexes) {
        x_sum += peaks[index].local_max_mz * peaks[index].local_max_height;
        y_sum += peaks[index].local_max_rt * peaks[index].local_max_height;
        height_sum += peaks[index].local_max_height;

        // NOTE(alex): This is a weighted average, it might cause problems if
        // the overall intensity between the files are very different (The
        // centroid will be biased towards the file with the greater average
        // intensity). If instead of a weighted average we want a density
        // average we could use the following:
        //
        //     x_sum += peaks[index].local_max_mz;
        //     y_sum += peaks[index].local_max_rt;
        //     height_sum += 1;
        //
        // This might have a problem where the noise could have a greater impact
        // in the position of the centroid.
    }
    cluster_mz = x_sum / height_sum;
    cluster_rt = y_sum / height_sum;
}

void MetaMatch::find_clusters(std::vector<MetaMatch::Peak>& peaks,
                              const MetaMatch::Parameters& parameters) {
    auto sort_peaks = [](auto p1, auto p2) -> bool {
        return (p1.local_max_mz < p2.local_max_mz) ||
               ((p1.local_max_mz == p2.local_max_mz) &&
                (p1.local_max_rt < p2.local_max_rt)) ||
               ((p1.local_max_rt == p2.local_max_rt) &&
                (p1.file_id < p2.file_id));
    };
    std::stable_sort(peaks.begin(), peaks.end(), sort_peaks);

    int cluster_id = 0;
    for (size_t i = 0; i < peaks.size(); ++i) {
        if (peaks[i].cluster_id != -1) {
            continue;
        }

        // Calculate initial centroid stats.
        double cluster_mz = 0;
        double cluster_rt = 0;
        std::vector<size_t> metapeak_indexes = {i};
        peaks[i].cluster_id = cluster_id;
        calculate_cluster_pos(cluster_mz, cluster_rt, peaks, metapeak_indexes);

        for (size_t j = (i + 1); j < peaks.size(); ++j) {
            // Since we know that the peaks are sorted monotonically in mz and
            // then rt, in order to calculate the maximum potential j we only
            // need to find the point where the peak.local_max_mz is above the
            // cluster radius.
            if (peaks[j].local_max_mz > cluster_mz + parameters.radius_mz) {
                break;
            }
            if (peaks[j].cluster_id == -1 &&
                (peaks[j].local_max_mz < cluster_mz + parameters.radius_mz &&
                 peaks[j].local_max_rt < cluster_rt + parameters.radius_rt)) {
                // If the cluster already contains a peak from the same file as
                // peaks[j], check if height of said peak is greater than
                // peaks[j].local_max_height, if it is, swap the index,
                // otherwise, continue.
                bool file_found = false;
                for (auto& index : metapeak_indexes) {
                    if (peaks[index].file_id == peaks[j].file_id) {
                        file_found = true;
                        if (peaks[index].file_id == peaks[j].file_id &&
                            peaks[index].local_max_height <
                                peaks[j].local_max_height) {
                            // Update cluster peaks.
                            peaks[index].cluster_id = -1;
                            index = j;
                            peaks[index].cluster_id = cluster_id;
                            break;
                        }
                    }
                }
                if (!file_found) {
                    peaks[j].cluster_id = cluster_id;
                    metapeak_indexes.push_back(j);
                }
                calculate_cluster_pos(cluster_mz, cluster_rt, peaks,
                                      metapeak_indexes);

                // Cull far peaks.
                for (int k = metapeak_indexes.size() - 1; k >= 0; --k) {
                    auto& index = metapeak_indexes[k];
                    if (peaks[index].local_max_mz >
                            cluster_mz + parameters.radius_mz ||
                        peaks[index].local_max_mz <
                            cluster_mz - parameters.radius_mz ||
                        peaks[index].local_max_rt >
                            cluster_rt + parameters.radius_rt ||
                        peaks[index].local_max_rt <
                            cluster_rt - parameters.radius_rt) {
                        peaks[index].cluster_id = -1;
                        metapeak_indexes.erase(metapeak_indexes.begin() + k);
                        calculate_cluster_pos(cluster_mz, cluster_rt, peaks,
                                              metapeak_indexes);
                    }
                }
            }
        }

        // Check if there is enough hits from a class in order to consider the
        // cluster valid.
        std::vector<size_t> class_hits(parameters.class_maps.size());
        for (const auto& index : metapeak_indexes) {
            const auto& peak = peaks[index];
            for (size_t k = 0; k < class_hits.size(); ++k) {
                if (peak.class_id == parameters.class_maps[k].id) {
                    class_hits[k] += 1;
                    break;
                }
            }
        }
        bool fraction_achieved = false;
        for (size_t k = 0; k < class_hits.size(); ++k) {
            const auto& n_hits = class_hits[k];
            if (n_hits >= parameters.class_maps[k].required_hits &&
                n_hits != 0) {
                fraction_achieved = true;
                break;
            }
        }
        if (!fraction_achieved) {
            for (const auto& index : metapeak_indexes) {
                peaks[index].cluster_id = -1;
            }
        } else {
            for (const auto& index : metapeak_indexes) {
                peaks[index].cluster_mz = cluster_mz;
                peaks[index].cluster_rt = cluster_rt;
            }
            ++cluster_id;
        }
    }
}

std::vector<MetaMatch::Peak> MetaMatch::extract_orphans(
    std::vector<MetaMatch::Peak>& peaks) {
    std::vector<MetaMatch::Peak> orphans;
    // TODO(alex): Where does the sorting need to
    // happen?
    auto sort_by_cluster_id = [](auto p1, auto p2) -> bool {
        return p1.cluster_id < p2.cluster_id;
    };
    std::stable_sort(peaks.begin(), peaks.end(), sort_by_cluster_id);

    for (size_t i = 0; i < peaks.size(); ++i) {
        if (peaks[i].cluster_id != -1) {
            orphans.insert(orphans.end(), peaks.begin(), peaks.begin() + i);
            peaks.erase(peaks.begin(), peaks.begin() + i);
            break;
        }
    }
    return orphans;
}

std::vector<MetaMatch::Cluster> MetaMatch::reduce_cluster(
    std::vector<MetaMatch::Peak>& peaks, size_t n_files) {
    std::vector<MetaMatch::Cluster> clusters;
    // TODO(alex): Where does the sorting need to
    // happen?
    auto sort_by_cluster_id = [](auto p1, auto p2) -> bool {
        return p1.cluster_id < p2.cluster_id ||
               (p1.cluster_id == p2.cluster_id && p1.file_id < p2.file_id);
    };
    std::stable_sort(peaks.begin(), peaks.end(), sort_by_cluster_id);
    if (peaks.empty()) {
        return clusters;
    }

    int64_t cluster_id = 0;
    size_t k = 0;
    for (size_t i = 1; i < peaks.size(); ++i) {
        if (cluster_id != peaks[i].cluster_id) {
            MetaMatch::Cluster cluster = {};
            cluster.id = cluster_id;
            cluster.mz = peaks[i - 1].cluster_mz;
            cluster.rt = peaks[i - 1].cluster_rt;
            cluster.file_heights = std::vector<double>(n_files);
            double sum_height = 0.0;
            size_t hits = 0;
            for (size_t j = k; j < i; ++j) {
                auto file_id = peaks[j].file_id;
                cluster.file_heights[file_id] = peaks[j].local_max_height;
                sum_height += peaks[j].local_max_height;
                hits++;
            }
            cluster.avg_height = sum_height / hits;
            clusters.push_back(cluster);
            cluster_id = peaks[i].cluster_id;
            k = i;
        }
    }

    // Sort clusters by highest average height and change cluster ids
    // accordingly.
    auto sort_by_avg_height = [](auto c1, auto c2) -> bool {
        return c1.avg_height > c2.avg_height;
    };
    std::stable_sort(clusters.begin(), clusters.end(), sort_by_avg_height);
    size_t i = 0;
    for (auto& cluster : clusters) {
        cluster.id = i;
        i++;
    }

    return clusters;
}