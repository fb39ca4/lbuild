# lbuild: generic, modular code generation in Python 3 [![][travis-svg]][travis]

The Library Builder (pronounced *lbuild*) is a BSD licensed [Python 3.5 tool][python]
for describing repositories containing modules which can copy or generate a set
of files based on the user provided data and options.

*lbuild* allows splitting up complex code generation projects into smaller
modules with configurable options, and provides for their transparent
discovery, documentation and dependency management.
Each module is written in Python 3 and declares its options and how to generate
its content via the [Jinja2 templating engine][jinja2] or a file/folder copy.

You can [install *lbuild* via PyPi][pypi]: `pip install lbuild`

Projects using *lbuild*:

- [modm generates a HAL for hundreds of embedded devices][modm] using *lbuild*
  and a data-driven code generation pipeline.

The dedicated maintainer of *lbuild* is [@salkinium][salkinium].


## Overview

Consider this repository:

```
 $ lbuild discover-modules
Parser(lbuild)
╰── Repository(repo @ ../repo)
    ├── EnumerationOption(option) = value
    ├── Module(repo:module)
    │   ├── BooleanOption(option) = True
    │   ├── Module(repo:module:submodule)
    │   │   ╰── SetOption(option)
    │   ╰── Module(repo:module:submodule2)
    ╰── Module(modm:module2)
```

*lbuild* is called by the user with a configuration file which contains the
repositories to scan, the modules to include and the options to configure
them with:

```xml
<library>
  <repositories>
    <repository><path>../repo/repo.lb</path></repository>
  </repositories>
  <options>
    <option name="repo:option">value</option>
    <option name="repo:module:option">1,2,3</option>
  </options>
  <modules>
    <module>repo:module</module>
  </modules>
</library>
```

The `repo.lb` file is compiled by *lbuild* and the two functions `init`,
`prepare` are called:

```python
def init(repo):
    repo.name = "repo"
    repo.add_option(EnumerationOption(name="option", enumeration=["value", "special"]))

def prepare(repo, options):
    repo.find_modules_recursive("src")
```

This gives the repository a name and declares a string option. The prepare step
adds all module files in the `src/` folder.

Each `module.lb` file is then compiled by *lbuild*, and the three functions
`init`, `prepare` and `build` are called:

```python
def init(module):
    module.parent = "repo"
    module.name = "module"

def prepare(module, options):
    if options["repo:option"] == "value":
        module.add_option(SetOption(name="option", enumeration=[1, 2, 3, 4, 5]))
        return True
    return False

def build(env):
    env.outbasepath = "repo/module"
    env.copy("static.hpp")
    for number in env["repo:module:option"]:
        env.template("template.cpp.in", "template_{}.cpp".format(number))
```

The init step sets the module's name and its parent name. The prepare step
then adds a `SetOption` and makes the module available, if the repository option
is set to `"value"`. Finally in the build step, a number of files are generated
based on the option's content.

The files are generated at the call-site of `lbuild build` which would then
look something like this:

```
 $ ls
main.cpp        project.xml
 $ lbuild build
 $ tree
.
├── main.cpp
├── repo
│   ├── module
│   │   ├── static.hpp
│   │   ├── template_1.cpp
│   │   ├── template_2.cpp
│   │   └── template_3.cpp
```


## Documentation

The above example shows a minimal feature set, but *lbuild* has a few more
tricks up its sleeves. Let's have a look at the API in more detail with examples
from [the modm repository][modm].


### Command Line Interface

Before you can build a project you need to provide a configuration.
*lbuild* aims to make discovery easy from the command line:

```
 $ lbuild --repository ../modm/repo.lb discover
Parser(lbuild)
╰── Repository(modm @ ../modm)   modm: a barebone embedded library generator
    ╰── EnumerationOption(target) = REQUIRED in [at90can128, at90can32, at90can64, ...
```

This gives you an overview of the repositories and their options. In this case
the `modm:target` repository option is required, so let's check that out:

```
 $ lbuild -r ../modm/repo.lb discover-options
modm:target = REQUIRED in [at90can128, at90can32, at90can64, at90pwm1, at90pwm161, at90pwm2,
                           ... a really long list ...
                           stm32l4s9vit, stm32l4s9zij, stm32l4s9zit, stm32l4s9ziy]

  Meta-HAL target device
```

You can then choose this repository option and discover the available modules
for this specific repository option:

```
 $ lbuild -r ../modm/repo.lb --option modm:target=stm32f407vgt discover
Parser(lbuild)
╰── Repository(modm @ ../modm)   modm: a barebone embedded library generator
    ├── EnumerationOption(target) = stm32f407vgt in [at90can128, at90can32, at90can64, ...]
    ├── Module(modm:board)
    │   ╰── Module(modm:board:disco-f407vg)
    ├── Module(modm:build)
    │   ├── Option(build.path) = build/parent-folder in [String]
    │   ├── Option(project.name) = parent-folder in [String]
    │   ╰── Module(modm:build:scons)  SCons Build Script Generator
    │       ├── BooleanOption(info.build) = False in [True, False]
    │       ╰── EnumerationOption(info.git) = Disabled in [Disabled, Info, Info+Status]
    ├── Module(modm:platform)
    │   ├── Module(modm:platform:can)
    │   │   ╰── Module(modm:platform:can:1) CAN 1 instance
    │   │       ├── NumericOption(buffer.rx) = 32 in [1 .. 32 .. 65534]
    │   │       ╰── NumericOption(buffer.tx) = 32 in [1 .. 32 .. 65534]
    │   ├── Module(modm:platform:core)
    │   │   ├── EnumerationOption(allocator) = newlib in [block, newlib, tlsf]
    │   │   ├── NumericOption(main_stack_size) = 3040 in [256 .. 3040 .. 65536]
    │   │   ╰── EnumerationOption(vector_table_location) = fastest in [fastest, ram, rom]
```

You can now discover all module options in more detail:

```
 $ lbuild -r ../modm/repo.lb -D modm:target=stm32f407vgt discover-options
modm:target = stm32f407vgt in [at90can128, at90can32, at90can64, ...]

  Meta-HAL target device

modm:build:build.path = build/parent-folder in [String]

  Path to the build folder

modm:build:project.name = parent-folder in [String]

  Project name for executable
```

Or check out specific module and option descriptions:

```
 $ lbuild -r ../modm/repo.lb -D modm:target=stm32f407vgt discover -n :build
>> modm:build

# Build System Generators

This parent module defines a common set of functionality that is independent of
the specific build system generator implementation.

>>>> modm:build:project.name

# Project Name

The project name defaults to the folder name you're calling lbuild from.

Value: parent-folder
Inputs: [String]

>>>> modm:build:build.path

# Build Path

The build path is defaulted to `build/{modm:build:project.name}`.

Value: build/parent-folder
Inputs: [String]
```

The complete lbuild command line interface is available with `lbuild -h`.


### Configuration

Even though *lbuild* can be configured sorely via the command line, it is
strongly recommended to create a configuration file (default is `project.xml`)
which *lbuild* will search for in the current working directory.

```xml
<library>
  <repositories>
    <!-- Declare all your repository locations relative to this file here -->
    <repository><path>path/to/repo.lb</path></repository>
    <repository><path>path/to/repo2.lb</path></repository>
  </repositories>
  <!-- You can also inherit from another configfile. The options you specify
       here will be overwritten. -->
  <extends>path/to/config.xml</extends>
  <!-- A repository may provide aliases for configurations, so that you can
       use a string as well, instead of a path. This saves you from knowing
       exactly where the configuration file is stored in the repo.
       See also `repo.add_configuration(name, path)`. -->
  <extends>repo:name_of_config</extends>
  <options>
    <!-- Options are treated as key-value pairs -->
    <option name="repo:repo_option_name">value</option>
    <!-- A SetOption is the only one allowing multiple values -->
    <option name="repo:module:module_option_name">set, options, may, contain, commas</option>
  </options>
  <modules>
    <!-- You only need to declare the modules you are actively using.
         The dependencies are automatically resolved by lbuild. -->
    <module>repo:module</module>
    <module>repo:other_module:submodule</module>
  </modules>
</library>
```

On startup, *lbuild* will search the current working directory upwards for a
`lbuild.xml` file, which if found, is used as the base configuration, inherited
by all other configurations. This is very useful when several projects all
require the same repositories, and you don't want to specify each repository
path for each project.

```xml
<library>
  <repositories>
    <repository><path>path/to/common/repo.lb</path></repository>
  </repositories>
  <modules>
    <module>repo:module-required-by-all</module>
  </modules>
</library>
```

In the simplest case your project just `<extends>` this base config.

```xml
<library>
  <extends>repo:config-name</extends>
</library>
```


### Files Configuration

*lbuild* properly imports the declared repository and modules files, so you can
use everything that Python has to offer.
In addition to `import`ing your required modules, *lbuild* provides these
global functions and classes for use in all files:

- `localpath(path)`: remaps paths relative to the currently executing file.
  All paths are already interpreted relative to this file, but you can use this
  to be explicit.
- `repopath(path)`: remaps paths relative to the repository file. You should use
  this to reference paths that are not related to your module.
- `FileReader(path)`: reads the contents of a file and turns it into a string.
- `listify(obj)`: turns obj into a list, maps `None` to empty list.
- `{*}Option(...)`: classes for describing options, [see Options](#Options).


### Repositories

*lbuild* calls these three functions for any repository file:

- `init(repo)`: provides name, documentation and other global functionality.
- `prepare(repo, options)`: adds all module files for this repository.
- `build(env)` (*optional*): *only* called if at least one module within the
  repository is built. It is meant for actions that must be performed for *any*
  module, like generating a global header file, or adding to the include path.

```python
# You can use everything Python has to offer
import antigravity

def init(repo):
    # You must give your repository a name, and it must be unique within the
    # scope of your project as it is used for namespacing all modules
    repo.name = "name"
    # You can set a repository description here, either as an inline string
    repo.description = "Repository Description"
    # or as a multi-line string
    repo.description = """
Multiline description.

Use whatever markup you want, lbuild treats it all as text.
"""
    # or read it from a separate file altogether
    repo.description = FileReader("module.md")

    # lbuild displays the descriptions as-is, without any modification, however,
    # you can set a custom format handler to change this for your repo.
    # NOTE: Custom format handlers are applied to all modules and options.
    def format_description(node, description):
        # in modm there's unit test metadata in HTML comments, let's remove them
        description = re.sub(r"\n?<!--.*?-->\n?", "", description, flags=re.S)
        # forward this to the default formatter
        return node.format_description(node, description)
    repo.format_description = format_description

    # You can also format the short descriptions for the discover views
    def format_short_description(node, description):
        # Remove the leading # from the Markdown headers
        return node.format_short_description(node, description.replace("#", ""))
    repo.format_short_description = format_short_description

    # Add ignore patterns for all repository modules
    # ignore patterns follow fnmatch rules
    repo.add_ignore_patterns("*/*.lb", "*/board.xml")

    # Add Jinja2 filters for all repository modules
    # NOTE: the filter is namespaced with the repository! {{ "A" | modm.number }} -> 65
    repo.add_filter("number", lambda char: ord(char))

    # Add an alias for a internal configuration
    # NOTE: the configuration is namespaced with the repository! <extends>repo:config</extends>
    repo.add_configuration("config", "internal/path/to/config.xml")

    # See Options for more option types
    repo.add_option(StringOption(name="option", default="value"))

def prepare(repo, options):
    # Access repository options via the `options` resolver
    if options["repo:option"] == "value":
        # Adds module files directly, or via globbing, all paths relative to this file
        repo.add_modules("folder/module.lb", repo.glob("*/*/module.lb"))
    # Searches recursively starting at basepath, adding any file that
    # fnmatch(`modulefile`), while ignoring fnmatch(`ignore`) patterns
    repo.add_modules_recursive(basepath=".", modulefile="*.lb", ignore="*/ignore/patterns/*")

def build(env):
    # Add the generated src/ to the metadata
    env.add_metadata("include_path", "src")
    # See module.build(env) for complete feature description.
```


### Modules

*lbuild* calls these five functions for any module file:

- `init(module)`: provides module name, parent and documentation.
- `prepare(module, options)`: enables modules, adds options and submodules by
  taking the repository options into consideration.
- `validate(env)` (*optional*): validate your inputs before building anything.
- `build(env)`: generate your library and add metadata to build log.
- `post_build(env, buildlog)` (*optional*): access the build log after the build
  step completed.

Module files are provided with these additional global classes:

- `Module`: Base class for generated modules.
- `ValidateException`: Exception to be raised when the `validate(env)` step fails.

Note that in contrast to a repository, modules must return a boolean from the
`prepare(module, options)` function, which indicates that the module is available
for the repository option configuration. This allows for modules to "share" a
name, but have completely different implementations.

The `validate(env)` step is used to validate the input for the build step,
allowing for computations that can fail to raise a `ValidateException("reason")`.
*lbuild* will collect these exceptions for all modules and display them
together before aborting the build. This step is performed before each build,
and you cannot generate any files in this step, only read the repository's state.
You can manually call this step via the `lbuild validate` command.

The `build(env)` step is where the actual file generation happens. Here you can
copy and generate files and folders from Jinja2 templates with the substitutions
of you choice and the configuration of the modules. Each file operation is
appended to a global build log, which you can also explicitly add metadata to.

The `post_build(env, buildlog)` step is meant for modules that need to generate
files which receive information from all built modules. The typically use-case
here is generating scripts for build systems, which need to know about what
files were generated and all module's metadata.

```python
def init(module):
    # give your module a name
    module.name = "name"
    # Each module has a parent, you can reference any module here. If you don't
    # set the module's parent, it is implicitly set to the repository
    module.parent = "repo:module"
    # You can set a module description here
    module.description = "Description"
    module.description = """Multiline"""
    module.description = FileReader("module.md")
    # modules can have their own formatters, works the same as for repositories
    module.format_description = custom_format_description
    module.format_short_description = custom_format_short_description
    # Add Jinja2 filters for this modules and all submodules
    # NOTE: the filter is namespace with the repository! {{ 65 | modm.character }} -> "A"
    module.add_filter("character", lambda number: chr(number))

def prepare(module, options):
    # Access repository options via the `options` resolver
    if options["repo:option"] == "value":
        # Returning False from this step disables this module
        return False

    # modules can depend on other modules
    module.depends("repo:module1", ":module2", ":module3:submodule", ...)

    # You can add more submodules in files
    module.add_submodule("folder/submodule.lb")

    # You can generate more modules here. This is useful if you have a lot of
    # very similar modules (like instances of hardware peripherals) that you
    # don't want to create a module file for each for.
    class Instance(Module):
        def __init__(self, instance):
            self.instance = instance
        def init(module):
            module.name = str(self.instance)
            # module.parent is automatically set!
        def prepare(module, options): ...
        def validate(env): ... # optional
        def build(env): ...
        def post_build(env): ... # optional

    # You can statically create and add these submodules
    for index in range(0, 5):
        module.add_submodule(Instance(index))
    # or make the creation dependent on a repository option
    for index in options["repo:instances"]:
        module.add_submodule(Instance(index))

    # See Options for more option types
    module.add_option(StringOption(name="option", default="world"))

    # Make this module available
    return True

# store data computed in validate step for build step.
build_data = None

# The validation step is optional
def validate(env):
    # Perform your input validations here
    # Access all options
    repo_option = env["repo:option"]
    defaulted_option = env.get("repo:module:option", default="hello")
    # Use proper logging instead of print() please
    # env.log.warning(...) and env.log.error(...) also available
    env.log.debug("Repo option: '{}'".format(repo_option))

    # You can query for options
    if env.has_option("repo:module:option") or env.has_module("repo:module"):
        env.log.info("Module option: '{}'".format(env["repo:module:option"]))

    # You can also use incomplete queries, see Name Resolution
    env.has_module(":module") # instead of repo:module
    env.has_option("::option") # repo:module:option
    # And use fnmatch queries
    # matches any module starting with `mod` and option starting with `name`.
    env.has_option(":mod*:name*")

    # You can raise a ValidationException if something is wrong
    if defaulted_option + repo_option != "hello world":
        raise ValidationException("Options are invalid because ...")

    # If you do heavy computations here for validation, you can store the
    # data in a global variable and reuse this for the build step
    build_data = defaulted_option * 2


# The build step can do everything the validation step can
# But now you can finally generate files
def build(env):
    # Set the output base path, this is relative to the lbuild invocation path
    env.outbasepath = "repo/module"

    # Copy single files
    env.copy("file.hpp")
    # Copy single files while renaming them
    env.copy("file.hpp", "cool_filename.hpp")
    # Relative paths are preserved!!!
    env.copy("../file.hpp") # copies to repo/file.hpp
    env.copy("../file.hpp", dest="file.hpp") # copies to repo/module/file.hpp

    # You can also copy entire folders
    env.copy("folder/", dest="renamed/")
    # and ignore specific RELATIVE files/folders
    env.copy("folder/", ignore=env.ignore_files("*.txt", "this_specific_file.hpp"))
    # or ignore specific ABSOLUTE paths
    env.copy("folder/", ignore=env.ignore_paths("*/folder/*.txt"))

    # You can also copy files out of a .zip or .tar archive
    env.extract("archive.zip") # everything inside the archive
    env.extract("archive.zip", dest="renamed/") # extract into folder
    # You can extract only parts of the archive, like a single file
    env.extract("archive.zip", src="filename.hpp", dest="renamed.hpp")
    # or an a single folder somewhere in the archive
    env.extract("archive.zip", src="folder/subfolder", dest="renamed/folder")
    # of course, you can ignore files and folders inside the archive too
    env.extract("archive.zip", src="folder", dest="renamed", ignore=env.ignore_files("*.txt"))

    # Set the global Jinja2 substitutions dictionary
    env.substitutions = {
        "hello": "world",
        "instances": map(str, env["repo:instances"]),
        "build_data": build_data, # from validation step
    }
    # and generate a file from a template
    env.template("template.hpp.in")
    # any `.in` postfix is automatically removed, unless you rename it
    for instance in env["repo:instances"]:
        env.template("template.hpp.in", "template_{}.hpp".format(instance))
    # You can explicitly add Jinja2 substitutions and filters
    env.template("template.hpp.in",
                 substitutions={"more": "subs"},
                 filters={"stringify": lambda i: str(i)})
    # Note: these filters are NOT namespaced with the repository name!

    # submodules are build first, so you can access the generated files
    headers = env.get_generated_local_files(lambda file: file.endswith(".hpp"))
    # and use this information for a new template.
    env.template("module_header.hpp.in", substitutions={"headers": headers})

    # You can add metadata to the build log which then made
    # available in the post_build step. This is like a dictionary.
    env.add_metadata("include_path", "generated_folder/")


# The post build step can do everything the build step can,
# but you can't add to the metadata anymore:
# - env.add_metadata() unavailable
# You have access to the entire buildlog up to this point
def post_build(env, buildlog):
    # The absolute path to the lbuild output directory
    outpath = buildlog.outpath

    # All modules that were built
    modules = buildlog.modules
    # All file generation operations that were done
    operations = buildlog.operations
    # All operations per module
    operations = buildlog.operations_per_module("repo:module")

    # iterate over all operations directly
    for operation in buildlog:
        # Get the module name that generated this file
        env.log.info("{} generated the '{}' file".format(
                     operation.module_name, operation.filename_out()))
        # You can also get the filename relative to a subfolder in outpath
        operation.filename_out(path="subfolder/")

    # get the metadata: this is a dictionary of lists!
    metadata = buildlog.metadata
    include_paths = [("-I" + p) for p in metadata.get("include_path", [])]
```

### Options

*lbuild* options are mappings from strings to Python objects.
Each option must have a unique name within their parent repository or module.
If you do not provide a default value, the option is marked as REQUIRED and
the project cannot be built without it.

Options can have a dependency handler which is called when the project
configuration is merged into the module options. It will give you the chosen
input value and you can return a number of module dependencies.

```python
def add_option_dependencies(value):
    if special_condition(value):
        # return single dependency
        return "repo:module"
    if other_special_condition(value):
        # return multiple dependencies
        return [":module1", "module2"]
    # No additional dependencies
    return None
```


#### StringOption

This is the most generic option, allowing to input any string.
The string is passed unmodified from the configuration to the module and the
dependency handler.

```python
option = StringOption(name="option-name",
                      description="inline", # or FileReader("file.md")
                      default="default string",
                      dependencies=add_option_dependencies)
```


#### BooleanOption

This option maps strings from `true`, `yes`, `1` to `bool(True)` and `false`,
`no`, `0` to `bool(False)`. The dependency handler is passed this `bool` value.

```python
option = BooleanOption(name="option-name",
                       description="boolean",
                       default=True,
                       dependencies=add_option_dependencies)
```


#### NumericOption

This option allows a number from [-Inf, +Inf]. You can limit this to the
range [minimum, maximum]. When using floating point numbers here, please be
aware that not all floating point numbers can be represented as a string
(like "1/3"). The dependency handler is passed a numeric value.

```python
option = NumericOption(name="option-name",
                       description="numeric",
                       minimum=0,
                       maximum=100,
                       default=50,
                       dependencies=add_option_dependencies)
```


#### EnumerationOption

This option maps a string to any generic Python object.
You can provide a list, set, tuple or range, the only limitation is that
the objects must be convertible to a string for unique identification.
If this is not possible, you can provide a dictionary with a manual mapping
from string to object. The dependency handler is passed the string value.

```python
option = EnumerationOption(name="option-name",
                           description="numeric",
                           # must be implicitly convertible to string!
                           enumeration=["value", 1, obj],
                           # or use a dictionary explicitly
                           enumeration={"value": "value", "1": 1, "obj": obj},
                           default="1",
                           dependencies=add_option_dependencies)
```


#### SetOption

This option is the same as the `EnumerationOption`, however, it is allowed to
contain multiple values from the enumeration as a set. The option will return a
list of Python objects. The dependency handler is passed a list of strings.

The set is represented in the configuration as a comma separated list.

```xml
<!-- Just one enumeration value is allowed -->
<option name=":module:enumeration-option">value</option>
<!-- Any set of enumeration values is allowed -->
<option name=":module:set-option">value, 1, obj</option>
```


### Jinja2 Configuration

*lbuild* uses the [Jinja2 template engine][jinja2] with the following global
configuration:

- Line statements start with `%% statement`.
- Line comments start with `%# comment`.
- Undefined variables throw an exception instead of being ignored.
- Global extensions: `jinja2.ext.do`.
- Global substitutions are:
  + `time`: `strftime("%d %b %Y, %H:%M:%S")`
  + `options`: an option resolver in the context of the current module.


### Name Resolution

*lbuild* manages repositories, modules and options in a tree structure and
serializes identification into unique string using `:` as hierarchy delimiters.
Any identifier provided via the command line, configuration, repository or
module files use the same resolver, which allows using *partially-qualified*
identifiers. In addition, globbing for multiple identifiers using fnmatch
semantics is supported.

The following rules for resolving identifiers apply:

1. A fully-qualified identifier specifies all parts: `repo:module:option`.
2. A partially-qualified identifier adds fnmatch wildcarts: `*:m.dule:opt*`.
3. `*` wildcarts for entire hierarchies can be ommitted: `::option`
4. A special wildcart is `:**`, which globs for everything below the current
   hierarchy level: `repo:**` selects all in `repo`, `repo:module:**` all in
   `repo:module`, etc.
5. Wildcarts are resolved in reverse hierarchical order. Therefore, `::option`
   may be unique within the context of `:module`, but not within the entire
   project.
6. For accessing direct children, you may specify their name without any
   delimiters: `option` within the context of `:module` will resolve to
   `:module:option`.

Partial identifiers were introduced to reduce verbosity and aid refactoring,
it is therefore recommended to:

1. Omit the repository name for accessing modules and options within the same
   repository.
2. Accessing a module's options with their name directly.


### Execution order

*lbuild* executes in this order:

1. `repository:init()`
2. Create repository options
3. `repository:prepare(repo-options)`
4. Find all modules in repositories
5. `module:init()`
6. `module:prepare(repo-options)`
7. Create module options
8. Resolve module dependencies
9. `module:validate(env)` submodules-first, *optional*
10. `module:build(env)` submodules-first
11. `repo:build(env)`: *optional*
12. `module:post_build(env)`: submodules-first, *optional*


[modm]: https://modm.io/how-modm-works
[jinja2]: http://jinja.pocoo.org
[python]: https://www.python.org
[pypi]: https://pypi.org/project/lbuild
[salkinium]: https://github.com/salkinium
[travis]: https://travis-ci.org/modm-io/lbuild
[travis-svg]: https://travis-ci.org/modm-io/lbuild.svg?branch=develop