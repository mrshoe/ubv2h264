CXX=aarch64-linux-gnu-g++
STRIP=aarch64-linux-gnu-strip
CFLAGS=-Wall -Wextra -Werror -ansi -pedantic -std=c++2a -Os -ffunction-sections -fdata-sections
LDFLAGS=-s -Wl,--gc-sections
EXEC=create_h264
SRC=$(wildcard *.cpp)
OBJ=$(SRC:.cpp=.o)

all: $(EXEC)

$(EXEC): $(OBJ)
	@$(CXX) -o $@ $^ $(LDFLAGS)
	@$(STRIP) --strip-all --remove-section=.comment --remove-section=.note $(EXEC)

%.o: %.c
	@$(CXX) -o $@ -c $< $(CFLAGS)

.PHONY: clean

clean:
	@rm -rf *.o
	@rm -rf $(EXEC)
