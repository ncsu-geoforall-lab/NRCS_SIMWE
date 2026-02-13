cmake_minimum_required(VERSION 3.16)
project(libsoil)

# Provide a CMake target so other addon CMakeLists can depend on this
add_library(libsoil INTERFACE)

# Allow the user to override the target install etc dir
if(NOT DEFINED ETC_DIR)
  set(ETC_DIR "${CMAKE_INSTALL_PREFIX}/etc")
endif()

# Python modules to install (list module filenames located in this dir)
set(MODULES __init__ soillib)

# Convert module names to filenames
set(PYFILES "")
foreach(m ${MODULES})
  list(APPEND PYFILES "${CMAKE_CURRENT_SOURCE_DIR}/${m}.py")
endforeach()

# Install each python file to ${ETC_DIR}/r.soildb
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/
        DESTINATION "${ETC_DIR}/r.soildb"
        FILES_MATCHING
        PATTERN "*.py"
        PATTERN "*.pyc" EXCLUDE)  # optionally include .pyc if desired

# If you prefer explicit files instead of directory install:
# install(FILES ${PYFILES} DESTINATION "${ETC_DIR}/r.soildb")

# Provide a convenient install target for packaging
set(CPACK_PACKAGE_NAME "r_soildb")
include(CPack)

# Convenience target to install directly into a GRASS addons directory
# Defaults to $HOME/.grass8/addons but can be overridden with -DGRASS_ADDON_DIR=...
if(NOT DEFINED GRASS_ADDON_DIR)
  if(DEFINED ENV{HOME})
    set(GRASS_ADDON_DIR "$ENV{HOME}/.grass8/addons")
  else()
    set(GRASS_ADDON_DIR "${CMAKE_INSTALL_PREFIX}")
  endif()
endif()

set(GRASS_ADDON_ETC_DIR "${GRASS_ADDON_DIR}/etc/r.soildb")

add_custom_target(install_addon
  COMMENT "Install libsoil into GRASS addons directory (${GRASS_ADDON_ETC_DIR})"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${GRASS_ADDON_ETC_DIR}"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "${CMAKE_CURRENT_SOURCE_DIR}/soillib.py"
          "${GRASS_ADDON_ETC_DIR}/soillib.py"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "${CMAKE_CURRENT_SOURCE_DIR}/__init__.py"
          "${GRASS_ADDON_ETC_DIR}/__init__.py"
)

# Provide a message showing how to use the convenience target
message(STATUS "To install into your GRASS addons dir run: cmake --build . --target install_addon")
