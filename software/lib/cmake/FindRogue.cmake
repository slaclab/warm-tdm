SET (Rogue_FIND_QUIETLY TRUE)
SET (Rogue_FIND_REQUIRED TRUE)

IF(NOT Rogue_FOUND)
	FIND_PATH(Rogue_INCLUDE_DIR rogue/LibraryBase.h
              PATHS $ENV{RogueROOT}/include
              NO_DEFAULT_PATH)
	FIND_PATH(Rogue_INCLUDE_DIR rogue/LibraryBase.h)
	if(Rogue_INCLUDE_DIR)
		SET(Rogue_INCLUDE_DIR "${Rogue_INCLUDE_DIR}" CACHE PATH "Path to Rogue headers" FORCE)
	endif()
	FIND_LIBRARY(Rogue_LIBRARIES NAMES rogue-core
	             PATHS $ENV{RogueROOT}/lib
	             NO_DEFAULT_PATH)
	FIND_LIBRARY(Rogue_LIBRARIES NAMES rogue-core)
	GET_FILENAME_COMPONENT(Rogue_LIB_DIR ${Rogue_LIBRARIES} PATH)
	INCLUDE (FindPackageHandleStandardArgs)
	FIND_PACKAGE_HANDLE_STANDARD_ARGS(Rogue DEFAULT_MSG Rogue_LIBRARIES Rogue_INCLUDE_DIR)

	if(Rogue_FOUND)
		SET(ROGUE_INCLUDE_DIRS "${Rogue_INCLUDE_DIR}" CACHE PATH "Path to Rogue headers" FORCE)
		SET(ROGUE_LIBRARIES "${Rogue_LIBRARIES}" CACHE PATH "Rogue libraries" FORCE)
		SET(Rogue_CXXFLAGS "-I${Rogue_INCLUDE_DIR}")
		SET(Rogue_LDFLAGS "${Rogue_LIBRARIES}")
		MESSAGE(STATUS "Found Rogue:")
		MESSAGE(STATUS "  * includes: ${Rogue_INCLUDE_DIR}")
		MESSAGE(STATUS "  * libs:     ${Rogue_LIBRARIES}")
	endif()
    
ENDIF(NOT Rogue_FOUND)