MODULE_TOPDIR =../..

PGM = r.soildb

SUBDIRS = libsoil \
          r.in.ssurgo

include $(MODULE_TOPDIR)/include/Make/Dir.make

default: parsubdirs htmldir

install: installsubdirs
	$(INSTALL_DATA) $(PGM).html $(INST_DIR)/docs/html/
