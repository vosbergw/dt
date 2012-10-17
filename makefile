
# use 'sudo make install' to install dt in /usr/local/bin

DEST=/usr/local/bin

install: ${DEST}/dt

/usr/local/bin/dt: src/dt.py
	install src/dt.py ${DEST}/dt
