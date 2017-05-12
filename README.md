TacoFountain
============
A [FountainAPI](https://github.com/FountainMC/FountainAPI) implementation
built on top of [TacoSpigot](https://github.com/TacoSpigot/TacoSpigot),
[Paper](https://github.com/PaperMC/Paper), and [Craftbukkit](https://www.spigotmc.org/).

## Features
- Backwards Compatible
  - All bukkit plugins should work alongside Fountain ones,
    even plugins that use NMS and reflection.
  - This makes using Fountain in production far more practical,
    as you can already use your existing bukkit plugins.
  - Compatibility is the foremost goal of this implementation,
    and it should cause minimal breakage to bukkit plugins.
- Stable
  - Spigot is very robust, and is used for some of the world's largest servers.
  - Paper builds upon this, adding even more fixes and
- Fast
  - Craftbukkit and Spigot have years worth of major performance improvements,
    increasing server scalibility far beyond that of vanilla and Forge.
  - Paper improves upon this even more, with many major optimizations.
  - TacoSpigot adds another layer of optimization, though not as big as Paper.

## Compiling
TacoFountain uses yet another project-specific build system,
built on top of TacoSpigot and Paper's systems.
Traditional patch files are used to store changes to the NMS code,
like in Craftbukkit. Using git patches is unnecessarily complex,
since all the patches are tied together and will never be sent upstream.

### Commands
Build commands can be run by invoking `fountain.sh`.
- `fountain.sh setup` - Setup the development environement, re-applying all the Paper and TacoSpigot patches.
  - This is needed in order to refresh the TaocoSpigot and Paper patches
- `fountain.sh patch` - Applies the patch files to the working directory, _overriding any existing work_
- `fountain.sh diff` - Regenerates the patch files from the contents of the working directory
  - This should be run periodically in order to save your work, in case you accidently run the patch command.
- `fountain.sh build-illegal` - Build an 'illegal' Fountain jar which violates the DCMA.
  - Although it's technically legal to use this jar on your own computer,
     it to somone else is illegal without first packaging it with Paperclip.
  - This is useful for development builds since it shaves up to a minute of the build time,
    and you don't need Paperclip when you're testing on your own computer.
- `fountain.sh build` - Build a Fountian jar packaged with Paperclip, which is fully legal and circumvents the DMCA.

### Requirements
- Bash unix environement with coreutils
- Python 3.6
  - The build system itself is written in python,
    and automatically bootstraps and downloads dependencies from pip.
- Git
- JDK 8
- Maven
