#ifndef TAPP_GRID_WEIGHTEDMESH_HPP
#define TAPP_GRID_WEIGHTEDMESH_HPP

#include <vector>

#include "tapp-grid.hpp"
#include "tapp-mesh.hpp"

// This class extends the base Mesh class with addition mWeights, and mCounts data
// fields and the functions necessary for its manipulation.
class WeightedMesh : public Mesh {
   protected:
    std::vector<double> mWeights;
    std::vector<unsigned int> mCounts;

   public:
    WeightedMesh(Grid::Dimensions dimensions = {}, Grid::Bounds bounds = {});

    // Getter methods for mWeights and mCounts.
    std::optional<double> weightAt(unsigned int i, unsigned int j);
    std::optional<double> countsAt(unsigned int i, unsigned int j);

    // This method will set the value stored at the given index to be proportional
    // to the existing value on that position and the given weight, incrementing
    // in turn the counter on the same position.
    bool set(unsigned int i, unsigned int j, double value, double weight);

    // Prints the mesh to std::out for debugging purposes.
    void printAll();

    // TODO(alex): Indexing functions should probably be part of the Grid interface.
    // Get the x index of the closest point (rounded down) for a given mz.
    std::optional<unsigned int> xIndex(double mz);

    // Get the y index of the closest point (rounded down) for a given rt.
    std::optional<unsigned int> yIndex(double rt);
};

#endif /* TAPP_GRID_WEIGHTEDMESH_HPP */
