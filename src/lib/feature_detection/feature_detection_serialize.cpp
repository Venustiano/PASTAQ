#include "feature_detection/feature_detection_serialize.hpp"
#include "utils/serialization.hpp"

bool FeatureDetection::Serialize::read_feature(std::istream &stream,
                                               Feature *feature) {
    Serialization::read_uint64(stream, &feature->id);
    Serialization::read_double(stream, &feature->rt);
    Serialization::read_double(stream, &feature->monoisotopic_mz);
    Serialization::read_double(stream, &feature->monoisotopic_height);
    Serialization::read_double(stream, &feature->average_mz);
    Serialization::read_double(stream, &feature->total_height);
    Serialization::read_vector<uint64_t>(stream, &feature->peak_ids,
                                         Serialization::read_uint64);
    return stream.good();
}

bool FeatureDetection::Serialize::write_feature(std::ostream &stream,
                                                const Feature &feature) {
    Serialization::write_uint64(stream, feature.id);
    Serialization::write_double(stream, feature.rt);
    Serialization::write_double(stream, feature.monoisotopic_mz);
    Serialization::write_double(stream, feature.monoisotopic_height);
    Serialization::write_double(stream, feature.average_mz);
    Serialization::write_double(stream, feature.total_height);
    Serialization::write_vector<uint64_t>(stream, feature.peak_ids,
                                          Serialization::write_uint64);
    return stream.good();
}
