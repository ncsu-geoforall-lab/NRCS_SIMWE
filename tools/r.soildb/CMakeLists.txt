cmake_minimum_required(VERSION 3.22)

project(r.soilsdb)

include(build_addon)

build_addon(
  ${PROJECT_NAME}
  ADDONS
    r.in.ssurgo
  DOCFILES
    r.in.ssurgo.html
    r.in.ssurgo.md)
