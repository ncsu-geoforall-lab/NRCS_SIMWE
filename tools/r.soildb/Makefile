MODULE_TOPDIR =../..

PGM = r.soildb

SUBDIRS = libstac \
        v.in.sda.soils \
        v.in.ssurgo \
        r.in.soilgrids \

include $(MODULE_TOPDIR)/include/Make/Dir.make

default: parsubdirs htmldir

install: installsubdirs
	$(INSTALL_DATA) $(PGM).html $(INST_DIR)/docs/html/
