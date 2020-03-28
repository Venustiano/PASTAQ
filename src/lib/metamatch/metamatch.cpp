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
        double mz = peaks[index].fitted_mz;
        double rt = peaks[index].fitted_rt + peaks[index].rt_delta;
        x_sum += mz * peaks[index].fitted_height;
        y_sum += rt * peaks[index].fitted_height;
        height_sum += peaks[index].fitted_height;

        // NOTE(alex): This is a weighted average, it might cause problems if
        // the overall intensity between the files are very different (The
        // centroid will be biased towards the file with the greater average
        // intensity). If instead of a weighted average we want a density
        // average we could use the following:
        //
        //     x_sum += peaks[index].fitted_mz;
        //     y_sum += peaks[index].fitted_rt;
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
        double p1_mz = p1.fitted_mz;
        double p2_mz = p2.fitted_mz;
        double p1_rt = p1.fitted_rt + p1.rt_delta;
        double p2_rt = p2.fitted_rt + p2.rt_delta;
        return (p1_mz < p2_mz) || ((p1_mz == p2_mz) && (p1_rt < p2_rt)) ||
               ((p1_rt == p2_rt) && (p1.file_id < p2.file_id));
    };
    std::sort(peaks.begin(), peaks.end(), sort_peaks);

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
            // need to find the point where the peak.fitted_mz is above the
            // cluster radius.
            if (peaks[j].fitted_mz > cluster_mz + parameters.radius_mz) {
                break;
            }
            double peak_mz = peaks[j].fitted_mz;
            double peak_rt = peaks[j].fitted_rt + peaks[j].rt_delta;
            if (peaks[j].cluster_id == -1 &&
                (peak_mz < cluster_mz + parameters.radius_mz &&
                 peak_rt < cluster_rt + parameters.radius_rt)) {
                // If the cluster already contains a peak from the same file as
                // peaks[j], check if height of said peak is greater than
                // peaks[j].fitted_height, if it is, swap the index,
                // otherwise, continue.
                bool file_found = false;
                for (auto& index : metapeak_indexes) {
                    if (peaks[index].file_id == peaks[j].file_id) {
                        file_found = true;
                        if (peaks[index].file_id == peaks[j].file_id &&
                            peaks[index].fitted_height <
                                peaks[j].fitted_height) {
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
                    double peak_mz = peaks[index].fitted_mz;
                    double peak_rt =
                        peaks[index].fitted_rt + peaks[index].rt_delta;
                    if (peak_mz > cluster_mz + parameters.radius_mz ||
                        peak_mz < cluster_mz - parameters.radius_mz ||
                        peak_rt > cluster_rt + parameters.radius_rt ||
                        peak_rt < cluster_rt - parameters.radius_rt) {
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
    std::sort(peaks.begin(), peaks.end(), sort_by_cluster_id);

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
    std::sort(peaks.begin(), peaks.end(), sort_by_cluster_id);
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
            cluster.file_volumes = std::vector<double>(n_files);
            double sum_height = 0.0;
            size_t hits = 0;
            for (size_t j = k; j < i; ++j) {
                auto file_id = peaks[j].file_id;
                cluster.file_heights[file_id] = peaks[j].fitted_height;
                cluster.file_volumes[file_id] = peaks[j].fitted_volume;
                sum_height += peaks[j].fitted_height;
                hits++;
                cluster.peak_ids.push_back({file_id, peaks[j].id});
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
    std::sort(clusters.begin(), clusters.end(), sort_by_avg_height);
    size_t i = 0;
    for (auto& cluster : clusters) {
        cluster.id = i;
        i++;
    }

    return clusters;
}

// Returns a vector of non owning pointers. For read use only. It assumes that
// the peaks in `feature' are contained in the given `peaks' vector and the
// latter is sorted by peak id.
std::vector<Centroid::Peak*> peaks_from_feature(
    FeatureDetection::Feature& feature, std::vector<Centroid::Peak>& peaks) {
    std::vector<Centroid::Peak*> peak_refs;
    if (peaks.empty()) {
        return {};
    }
    for (const auto peak_id : feature.peak_ids) {
        size_t left = 0;
        size_t right = peaks.size();
        while (left < right) {
            size_t mid = left + ((right - left) / 2);
            if (peaks[mid].id < peak_id) {
                left = mid + 1;
            } else {
                right = mid;
            }
        }
        if (right < peaks.size() && peaks[right].id == peak_id) {
            peak_refs.push_back(&peaks[right]);
        }
    }
    return peak_refs;
}

// Calculates the cosine similarity of two sets of vectors. Note that the peaks
// might not necessarily be aligned, so we must first find the equivalence of
// the peaks for both vectors.
double find_feature_overlap(std::vector<Centroid::Peak*>& ref_peaks,
                            std::vector<Centroid::Peak*>& feature_peaks) {
    // TODO: ...
    return 0;
}

std::vector<MetaMatch::FeatureCluster> find_feature_clusters_new(
    std::vector<MetaMatch::InputSetFeatures>& input_sets, double keep_perc) {
    // We need two sets of indexes, one sorted in descending order of intensity
    // to prioritize the seletion of a reference feature to match to, and a set
    // of indexes per file to sort by ascending retention time order. This is
    // done to speedup searching of features using binary search.
    struct Index {
        uint64_t file_index;
        uint64_t group_id;
        uint64_t feature_index;
        double retention_time;
        double intensity;
    };

    // Find the total number of features and prepare index vectors.
    auto available_features = std::vector<std::vector<bool>>(input_sets.size());
    auto feature_lists = std::vector<std::vector<Index>>(input_sets.size());
    std::vector<Index> all_features;
    for (size_t i = 0; i < input_sets.size(); ++i) {
        auto& input_set = input_sets[i];
        available_features[i] =
            std::vector<bool>(input_set.features.size(), true);
        feature_lists[i] = std::vector<Index>(input_set.features.size());
        for (size_t j = 0; j < input_set.features.size(); ++j) {
            feature_lists[i][j] = {i, input_set.group_id, j,
                                   input_set.features[j].average_rt,
                                   input_set.features[j].total_volume};
        }
        // Copy feature_lists[i] to the end of all_features.
        all_features.insert(all_features.end(), feature_lists[i].begin(),
                            feature_lists[i].end());

        // Further parts of the algorithm need peak files to be sorted by id.
        // This should be the default, but it is not guaranteed.
        std::sort(input_set.peaks.begin(), input_set.peaks.end(),
                  [](auto a, auto b) -> bool { return a.id < b.id; });
    }

    // Sort all_features by intensity and feature_lists by retention time.
    std::sort(all_features.begin(), all_features.end(),
              [](auto a, auto b) -> bool { return a.intensity > b.intensity; });
    for (auto& feature_list : feature_lists) {
        std::sort(feature_list.begin(), feature_list.end(),
                  [](auto a, auto b) -> bool {
                      return a.retention_time < b.retention_time;
                  });
    }

    // Start the matching.
    std::vector<MetaMatch::FeatureCluster> clusters;
    for (size_t i = 0; i < all_features.size(); ++i) {
        auto& ref_feature_index = all_features[i];
        auto ref_file_index = ref_feature_index.ref_file_index;
        auto feature_index = ref_feature_index.feature_index;
        // Check availability.
        if (!available_features[ref_file_index][feature_index]) {
            continue;
        }
        // Get the peaks for the reference feature.
        auto& ref_feature = input_sets[ref_file_index].features[feature_index];
        auto ref_peaks =
            peaks_from_feature(ref_feature, input_sets[ref_file_index].peaks);
        if (ref_peaks.empty()) {
            continue;
        }

        // Calculate the boundary region for this feature.
        size_t n = ref_peaks.size();
        double ref_min_mz =
            ref_peaks[0]->fitted_mz - 3 * ref_peaks[0]->fitted_sigma_mz;
        double ref_max_mz =
            ref_peaks[n - 1]->fitted_mz + 3 * ref_peaks[0]->fitted_sigma_mz;
        double ref_min_rt =
            ref_feature.average_rt - 3 * ref_feature.average_rt_sigma;
        double ref_max_rt =
            ref_feature.average_rt + 3 * ref_feature.average_rt_sigma;

        // NOTE: Currently storing the feature index instead of the the feature
        // ids for performance. If we are to keep this cluster, this should be
        // swapped.
        std::vector<FeatureId> features_in_cluster;
        features_in_cluster.push_back({ref_file_id, ref_feature_index});
        for (size_t j = 0; j < feature_lists.size(); ++j) {
            if (j == ref_file_index) {
                continue;
            }
            const auto& feature_list = feature_lists[j];
            const auto& input_set = input_set[j];
            // Find features within the retention time ROI.
            size_t left = 0;
            size_t right = feature_list.size();
            while (left < right) {
                size_t mid = left + ((right - left) / 2);
                if (feature_list[mid].retention_time < ref_min_rt) {
                    left = mid + 1;
                } else {
                    right = mid;
                }
            }
            size_t min_k = right;
            if (right > feature_list.size() ||
                feature_list[min_k].retention_time > ref_max_rt) {
                continue;
            }

            // Keep track of the best candidate for this file.
            double best_overlap = 0;
            size_t best_index = 0;
            for (size_t k = min_k; k < feature_list.size(); ++k) {
                if (feature_list[k].retention_time > ref_max_rt) {
                    break;
                }
                size_t feature_index = feature_list[k].feature_index;
                auto& feature = input_set.features[feature_index];

                // We are using point-in-rectangle check instead of intersection
                // of boundaries to determine if two features are in range for
                // further processing.
                if (feature.charge_state != ref_feature.charge_state ||
                    feature.average_mz < ref_min_mz ||
                    feature.average_mz > ref_max_mz ||
                    !available_features[j][feature_index]) {
                    continue;
                }

                // Find the peaks for this feature.
                auto feature_peaks =
                    peaks_from_feature(feature, input_set.peaks);
                if (feature_peaks.empty()) {
                    continue;
                }

                // Check the overlap between the reference and this feature.
                // If the overlap is greater than the previous one, swap it.
                double overlap = find_feature_overlap(ref_peaks, feature_peaks);
                if (overlap > best_overlap) {
                    best_overlap = overlap;
                    best_index = feature_index;
                }
            }
            if (best_overlap > overlap_threshold) {
                features_in_cluster.push_back({j, best_index});
            }
        }
        if (features_in_cluster.empty()) {
            continue;
        }

        // Build cluster object.
        FeatureCluster cluster = {};
        cluster.charge_state = ref_feature.charge_state;
        std::vector<uint64_t> cluster_groups;
        for (auto& feature_id : features_in_cluster) {
            size_t file_id = feature_id.file_id;
            size_t feature_index = feature_id.feature_id;
            auto& feature = input_sets[file_id].features[feature_index];

            // Mark clustered features as not available.
            available_features[file_id][feature_index] = false;

            // Replace feature_index with its corresponding id.
            feature_id.feature_id = feature.id;

            // Keep track of the groups within this cluster.
            cluster_groups.push_back(input_sets[file_id].group_id);

            // Store some statistics about the cluster.
            cluster.mz += feature.average_mz;
            cluster.rt += feature.average_rt + feature.average_rt_delta;
            cluster.avg_total_height += feature.total_height;
            cluster.avg_monoisotopic_height += feature.monoisotopic_height;
            cluster.avg_max_height += feature.max_height;
            cluster.avg_total_volume += feature.total_volume;
            cluster.avg_monoisotopic_volume += feature.monoisotopic_volume;
            cluster.avg_max_volume += feature.max_volume;
            cluster.total_heights.push_back(feature.total_height);
            cluster.monoisotopic_heights.push_back(feature.monoisotopic_height);
            cluster.max_heights.push_back(feature.max_height);
            cluster.total_volumes.push_back(feature.total_volume);
            cluster.monoisotopic_volumes.push_back(feature.monoisotopic_volume);
            cluster.max_volumes.push_back(feature.max_volume);
        }
        cluster.mz /= features_in_cluster.size();
        cluster.rt /= features_in_cluster.size();
        cluster.avg_total_height /= features_in_cluster.size();
        cluster.avg_monoisotopic_height /= features_in_cluster.size();
        cluster.avg_max_height /= features_in_cluster.size();
        cluster.avg_total_volume /= features_in_cluster.size();
        cluster.avg_monoisotopic_volume /= features_in_cluster.size();
        cluster.avg_max_volume /= features_in_cluster.size();

        // Check if the given feature_ids selected for this cluster meet the
        // filter critera of a minimum number of samples for any given group.
        // For example, if we have three groups of 10 samples, with a
        // `keep_perc' of 0.7, we meet the nan percentage if in any of the three
        // groups we have at least 7 features being matched.
        // TODO: ...
        bool nan_criteria_met = false;
        if (nan_criteria_met) {
            clusters.push_back(cluster);
        }
    }

    return clusters;
}

std::vector<MetaMatch::FeatureCluster> MetaMatch::find_feature_clusters(
    std::vector<MetaMatch::InputSetFeatures>& input_sets) {
    std::vector<MetaMatch::FeatureCluster> clusters;
    // TODO: Do noise discrimination based on desired % per group.
    // 1.- Create an indexed set of the highest intensity peaks in descending
    //     order.
    // 2.- Find the highest intensity feature to start the algorithm.
    // 3.- Find the features within the region of interest ROI of the selected
    //     feature in each file. The search relies on another index, this time
    //     for retention time, sorted in ascending order.
    // 4.- Per file, select the candidate feature that maximizes the
    //     optimization metric (i.e. Maximum cumulative overlap).
    // 5.- Mark the selected candidates as taken and build the cluster object.
    // 6.- GOTO 2
    // 7.- Once done, go back to peak lists to find undetected features.

    // Find the total number of features.
    uint64_t num_features = 0;
    for (const auto& input_set : input_sets) {
        num_features += input_set.features.size();
    }

    // Create an index of the features in each file sorted by retention time in
    // ascending order.
    auto retention_time_index =
        std::vector<std::vector<Search::KeySort<double>>>(input_sets.size());

    // Keep track of which features are available, i.e. features that have not
    // been assigned a cluster yet.
    //     true: feature has been used
    //     false: feature have not been used
    auto availability_index = std::vector<std::vector<bool>>(input_sets.size());

    // We need to index the features to sort by descending intensity to
    // prioritize the next initial candidate.
    // FIXME: The name `file_id` might be confusing. Maybe `sample_id` is more
    // clear.
    struct Index {
        uint64_t file_id;
        uint64_t feature_id;
        double total_intensity;
    };
    auto feature_indexes = std::vector<Index>(num_features);

    // Build the index objects.
    size_t k = 0;
    for (size_t i = 0; i < input_sets.size(); ++i) {
        const auto& features = input_sets[i].features;
        retention_time_index[i] =
            std::vector<Search::KeySort<double>>(features.size());
        availability_index[i] = std::vector<bool>(features.size());
        for (size_t j = 0; j < features.size(); ++j, ++k) {
            feature_indexes[k].file_id = i;
            feature_indexes[k].feature_id = j;
            feature_indexes[k].total_intensity = features[j].total_height;
            retention_time_index[i][j] = {
                j, features[j].average_rt + features[j].average_rt_delta};
        }
        std::sort(retention_time_index[i].begin(),
                  retention_time_index[i].end(),
                  [](auto a, auto b) { return a.sorting_key < b.sorting_key; });
    }
    std::sort(feature_indexes.begin(), feature_indexes.end(),
              [](auto a, auto b) -> bool {
                  return a.total_intensity > b.total_intensity;
              });

    for (const auto& index : feature_indexes) {
        // Find the next available reference feature.
        size_t ref_file_id = index.file_id;
        size_t ref_feature_id = index.feature_id;
        if (availability_index[ref_file_id][ref_feature_id]) {
            continue;
        }
        const auto& ref = input_sets[ref_file_id].features[ref_feature_id];

        // Get the peaks corresponding with the reference feature.
        std::vector<Centroid::Peak> ref_peaks;
        for (const auto& peak_id : ref.peak_ids) {
            ref_peaks.push_back(input_sets[ref_file_id].peaks[peak_id]);
        }

        // Calculate ROI.
        double min_mz = ref_peaks[0].fitted_mz - 3 * ref.average_mz_sigma;
        double max_mz = ref_peaks[ref_peaks.size() - 1].fitted_mz +
                        3 * ref.average_mz_sigma;
        double min_rt =
            ref.average_rt + ref.average_rt_delta - 3 * ref.average_rt_sigma;
        double max_rt =
            ref.average_rt + ref.average_rt_delta + 3 * ref.average_rt_sigma;

        // Find the maximally similar feature in the rest of the files within
        // the ROI.
        std::vector<FeatureDetection::Feature*> clustered_features(
            input_sets.size());
        for (size_t file_id = 0; file_id < input_sets.size(); ++file_id) {
            if (ref_file_id == file_id) {
                clustered_features[file_id] =
                    &input_sets[ref_file_id].features[ref_feature_id];
                continue;
            }
            const auto& input_set = input_sets[file_id];
            auto& features = input_set.features;
            size_t min_j =
                Search::lower_bound(retention_time_index[file_id], min_rt);
            size_t max_j = retention_time_index[file_id].size();
            double prev_cum_overlap = 0;
            for (size_t j = min_j; j < max_j; ++j) {
                auto feature_id = retention_time_index[file_id][j].index;
                if (retention_time_index[file_id][j].sorting_key > max_rt) {
                    break;
                }
                if (availability_index[file_id][feature_id]) {
                    continue;
                }
                auto& feature = features[feature_id];
                double mz = feature.average_mz;
                double sigma_mz = feature.average_mz_sigma;

                if ((mz + sigma_mz * 3) < min_mz ||
                    (mz - sigma_mz * 3) > max_mz) {
                    continue;
                }

                // Feature is within ROI. Calculate gaussian overlap of the
                // peaks from this feature with the reference feature. We will
                // keep the feature that maximizes the overlap with the
                // reference.
                std::vector<Centroid::Peak> feature_peaks;
                for (const auto& peak_id : feature.peak_ids) {
                    auto peak = input_sets[file_id].peaks[peak_id];
                    feature_peaks.push_back(peak);
                }
                double cum_overlap =
                    Centroid::cumulative_overlap(ref_peaks, feature_peaks);
                if (cum_overlap > prev_cum_overlap) {
                    prev_cum_overlap = cum_overlap;
                    clustered_features[file_id] = &feature;
                }
            }
        }

        MetaMatch::FeatureCluster cluster = {};
        cluster.mz = 0.0;
        cluster.rt = 0.0;
        cluster.avg_height = 0.0;
        cluster.file_heights = std::vector<double>(clustered_features.size());
        for (size_t file_id = 0; file_id < clustered_features.size();
             ++file_id) {
            const auto& feature = clustered_features[file_id];
            if (feature == nullptr) {
                continue;
            }
            // FIXME: feature->id is UB if indices are not sequencial starting
            // at 0.
            // Mark the selected features as not available.
            availability_index[file_id][feature->id] = true;
            // Build cluster object.
            cluster.mz += feature->average_mz;
            cluster.rt += feature->average_rt;
            cluster.file_heights[file_id] = feature->total_height;
            cluster.avg_height += feature->total_height;
            cluster.feature_ids.push_back({file_id, feature->id});
        }
        if (cluster.feature_ids.size() <= 1) {
            continue;
        }
        cluster.mz /= cluster.feature_ids.size();
        cluster.rt /= cluster.feature_ids.size();
        cluster.avg_height /= cluster.feature_ids.size();
        cluster.charge_state = ref.charge_state;
        if (cluster.mz != 0 && cluster.rt != 0) {
            clusters.push_back(cluster);
        }
    }

    // Assign ids to clusters.
    for (size_t i = 0; i < clusters.size(); ++i) {
        clusters[i].id = i;
    }

    return clusters;
}
