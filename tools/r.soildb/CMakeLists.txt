cmake_minimum_required(VERSION 3.22)

project(r.soildb)

include(build_addon)

build_addon(
  ${PROJECT_NAME}
  ADDONS
    r.in.ssurgo
    libsoil
  DOCFILES
    r.soildb.html
    r.soildb.md)
