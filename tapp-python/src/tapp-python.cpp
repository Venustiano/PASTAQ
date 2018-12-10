#include <filesystem>
#include <fstream>
#include <iostream>

#include "grid/grid.hpp"
#include "grid/xml_reader.hpp"
#include "pybind11/numpy.h"
#include "pybind11/pybind11.h"
#include "pybind11/stl.h"

namespace py = pybind11;

struct Chromatogram {
    std::vector<double> retention_time;
    std::vector<double> intensity;
};

struct RawData {
    std::vector<Grid::Point> data;
    std::string file_name;
    // TODO: Store dimensions, instrument, min/max mz/rt

    // Extract the total ion chromatogram from the RawData.
    Chromatogram tic() {
        // Make a copy of the original data before sorting.
        std::vector<Grid::Point> points = data;

        // Sort the points by retention time.
        auto sort_points = [](const Grid::Point &p1,
                              const Grid::Point &p2) -> bool {
            return (p1.rt < p2.rt);
        };
        std::stable_sort(points.begin(), points.end(), sort_points);

        // Find the tic.
        Chromatogram tic = {};
        double previous_rt = -std::numeric_limits<double>::infinity();
        int i = -1;
        for (const auto &point : points) {
            if (point.rt > previous_rt || i == -1) {
                previous_rt = point.rt;
                tic.intensity.push_back(0);
                tic.retention_time.push_back(point.rt);
                ++i;
            }
            tic.intensity[i] += point.value;
        }
        return tic;
    }
};

RawData raw_data(std::string file_name, double min_mz, double max_mz,
                 double min_rt, double max_rt) {
    // Setup infinite range if no point was specified.
    min_rt = min_rt < 0 ? 0 : min_rt;
    max_rt = max_rt < 0 ? std::numeric_limits<double>::infinity() : max_rt;
    min_mz = min_mz < 0 ? 0 : min_mz;
    max_mz = max_mz < 0 ? std::numeric_limits<double>::infinity() : max_mz;

    // Sanity check the min/max rt/mz.
    if (min_rt >= max_rt) {
        std::ostringstream error_stream;
        error_stream << "error: min_rt >= max_rt (min_rt: " << min_rt
                     << ", max_rt: " << max_rt << ")";
        throw std::invalid_argument(error_stream.str());
    }
    if (min_mz >= max_mz) {
        std::ostringstream error_stream;
        error_stream << "error: min_mz >= max_mz (min_mz: " << min_mz
                     << ", max_mz: " << max_mz << ")";
        throw std::invalid_argument(error_stream.str());
    }

    std::filesystem::path input_file = file_name;

    // Check if the file exist.
    if (!std::filesystem::exists(input_file)) {
        std::ostringstream error_stream;
        error_stream << "error: couldn't find the file " << input_file;
        throw std::invalid_argument(error_stream.str());
    }

    // Open file stream.
    std::ifstream stream;
    stream.open(input_file);
    if (!stream) {
        std::ostringstream error_stream;
        error_stream << "error: couldn't open input file" << input_file;
        throw std::invalid_argument(error_stream.str());
    }

    // Read the data from the file.
    Grid::Parameters parameters = {
        {}, {min_rt, max_rt, min_mz, max_mz}, {}, 0x00, 0x00,
    };
    auto points = XmlReader::read_next_scan(stream, parameters);
    std::vector<Grid::Point> all_points = {};
    do {
        all_points.insert(end(all_points), begin(points.value()),
                          end(points.value()));
        points = XmlReader::read_next_scan(stream, parameters);
    } while (points != std::nullopt);

    return RawData{
        all_points,
        input_file.filename(),
    };
}

PYBIND11_MODULE(tapp, m) {
    // Documentation.
    m.doc() = "tapp documentation";

    // Structs.
    py::class_<Grid::Point>(m, "RawPoint")
        .def_readonly("mz", &Grid::Point::mz)
        .def_readonly("rt", &Grid::Point::rt)
        .def_readonly("value", &Grid::Point::value)
        .def("__repr__", [](const Grid::Point &p) {
            return "RawPoint {mz: " + std::to_string(p.mz) +
                   ", rt: " + std::to_string(p.rt) +
                   ", intensity: " + std::to_string(p.value) + "}";
        });

    py::class_<Chromatogram>(m, "Chromatogram")
        .def_readonly("intensity", &Chromatogram::intensity)
        .def_readonly("retention_time", &Chromatogram::retention_time);

    py::class_<RawData>(m, "RawData", py::buffer_protocol())
        .def_readonly("data", &RawData::data)
        .def("tic", &RawData::tic)
        .def_buffer([](RawData &m) -> py::buffer_info {
            return py::buffer_info(
                // Pointer to buffer.
                m.data.data(),
                // Size of one scalar.
                sizeof(double),
                // Format descriptor.
                py::format_descriptor<double>::format(),
                // Number of dimensions.
                2,
                // Number of elements in each dimension.
                {int(m.data.size()), 3},
                // Stride for each dimension (bytes).
                {sizeof(double) * (m.data.size() - 1), sizeof(double)});
        })
        .def("__repr__", [](const RawData &rd) {
            return "RawData {file_name: " + rd.file_name +
                   ", number_of_points: " + std::to_string(rd.data.size()) +
                   "}";
        });

    // Functions.
    m.def("raw_data", &raw_data, "Read raw data from the given mzXML file",
          py::arg("file_name"), py::arg("min_mz") = -1.0,
          py::arg("max_mz") = -1.0, py::arg("min_rt") = -1.0,
          py::arg("max_rt") = -1.0);
    m.def("dummy_test",
          []() {
              return RawData{{{1, 1.0, 1}, {1, 1.0, 1}, {1, 2.0, 2}},
                             "dummy.mzXML"};
          },
          "DEBUG: dummy test");
}