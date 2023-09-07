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
SET(CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)

if (DEFINED ENV{ROGUE_DIR})
   set(Rogue_DIR $ENV{ROGUE_DIR}/lib)
else()
   set(Rogue_DIR ${CMAKE_PREFIX_PATH}/lib)
endif()
find_package(Rogue REQUIRED)
find_package(S4DAQSender REQUIRED)

find_package(Python QUIET REQUIRED COMPONENTS Interpreter Development)
Message("-- Found Python version: ${Python_VERSION}")

set(Boost_PYTHON_TYPE python)
# Hack for some old Boost CMake modules
set(_Boost_PYTHON${Python_VERSION_MAJOR}_HEADERS "boost/python.hpp")
set(_Boost_PYTHON${Python_VERSION_MAJOR}${Python_VERSION_MINOR}_HEADERS "boost/python.hpp")

find_package(Boost QUIET COMPONENTS python${Python_VERSION_MAJOR}${Python_VERSION_MINOR})
if(${Boost_PYTHON${Python_VERSION_MAJOR}${Python_VERSION_MINOR}_FOUND})
	set(Boost_PYTHON_TYPE python${Python_VERSION_MAJOR}${Python_VERSION_MINOR})
else()
	find_package(Boost QUIET COMPONENTS python${Python_VERSION_MAJOR})
	if(${Boost_PYTHON${Python_VERSION_MAJOR}_FOUND})
		set(Boost_PYTHON_TYPE python${Python_VERSION_MAJOR})
	endif()
endif()
find_package(Boost REQUIRED COMPONENTS system ${Boost_PYTHON_TYPE})

#####################################
# Setup build
#####################################

# Include files
include_directories(${ROGUE_INCLUDE_DIRS} ${S4DAQSender_INCLUDE_DIRS} ${PROJECT_SOURCE_DIR}/include)

# Create rogue python library
add_library(warm_tdm_lib SHARED "")
target_include_directories(warm_tdm_lib PRIVATE ${Python_INCLUDE_DIRS} ${Boost_INCLUDE_DIRS})

add_subdirectory(src)
add_warm_tdm_sources(TARGET warm_tdm_lib PYTHON)

# Set output to TOP/lib, remove lib prefix
set_target_properties(warm_tdm_lib PROPERTIES PREFIX "" SUFFIX ".so")
set_target_properties(warm_tdm_lib PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/../python)

# Link to rogue core
TARGET_LINK_LIBRARIES(warm_tdm_lib PUBLIC ${ROGUE_LIBRARIES} ${S4DAQSender_LIBRARIES} ${Boost_LIBRARIES} ${Python_LIBRARIES})

# Create non-Python library
# This will currently compile the shared sources twice, which is suboptimal,
# but doesn't involve much code in total. One possible solution would be to
# build the python library from the native library.
add_library(warm_tdm_native SHARED "")
target_compile_definitions(warm_tdm_native PRIVATE "-DNO_PYTHON")
target_include_directories(warm_tdm_native PRIVATE)
add_warm_tdm_sources(TARGET warm_tdm_native)
TARGET_LINK_LIBRARIES(warm_tdm_native PUBLIC ${ROGUE_LIBRARIES} ${S4DAQSender_LIBRARIES})

#####################################
# Install Setup
#####################################

include(GNUInstallDirs)
install(TARGETS warm_tdm_native LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(DIRECTORY ${PROJECT_SOURCE_DIR}/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/s4_warm_tdm FILES_MATCHING PATTERN "*.h")