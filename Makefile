CXX=aarch64-linux-gnu-g++
STRIP=aarch64-linux-gnu-strip
CFLAGS=-Wall -Wextra -Werror -ansi -pedantic -std=c++2a -Os -ffunction-sections -fdata-sections
LDFLAGS=-s -Wl,--gc-sections
SRCDIR=src
BUILDDIR=build
EXEC=$(BUILDDIR)/ubv2h264
SRC=$(wildcard $(SRCDIR)/*.cpp)
OBJ=$(addprefix $(BUILDDIR)/,$(notdir $(SRC:.cpp=.o)))

all: $(BUILDDIR) $(EXEC)

$(BUILDDIR):
	@mkdir $@

$(EXEC): $(OBJ)
	@$(CXX) -o $@ $^ $(LDFLAGS)
	@$(STRIP) --strip-all --remove-section=.comment --remove-section=.note $(EXEC)

$(BUILDDIR)/%.o: $(SRCDIR)/%.cpp
	@$(CXX) -o $@ -c $< $(CFLAGS)

.PHONY: clean

clean:
	@rm -rf $(BUILDDIR)
