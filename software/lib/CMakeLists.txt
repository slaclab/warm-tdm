# contained in the LICENSE.txt file.
# ----------------------------------------------------------------------------

# Add support for building in conda environment
if (DEFINED ENV{CONDA_PREFIX})
   set(CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}")
   link_directories($ENV{CONDA_PREFIX}/lib)
endif()

# Check cmake version
cmake_minimum_required(VERSION 3.5)
include(InstallRequiredSystemLibraries)

# Project name
project (ucusc_hn_lib)

# C/C++
enable_language(CXX)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x -Wno-deprecated")

#####################################
# Find Rogue & Support Libraries
#####################################
if (DEFINED ENV{ROGUE_DIR})
   set(Rogue_DIR $ENV{ROGUE_DIR}/lib)
else()
   set(Rogue_DIR ${CMAKE_PREFIX_PATH}/lib)
endif()
find_package(Rogue REQUIRED)

#####################################
# Setup build
#####################################

# Include files
include_directories(${ROGUE_INCLUDE_DIRS} ${PROJECT_SOURCE_DIR}/include)

# Create rogue python library
add_library(ucsc_hn_lib SHARED "")

add_subdirectory(src)

# Set output to TOP/lib, remove lib prefix
set_target_properties(ucsc_hn_lib PROPERTIES PREFIX "" SUFFIX ".so")
set_target_properties(ucsc_hn_lib PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/../python)

# Link to rogue core
TARGET_LINK_LIBRARIES(ucsc_hn_lib PUBLIC ${ROGUE_LIBRARIES})

