# cudet
Python-based tool for Mirantis OpenStack, which provides the following info
about environments and the Fuel master server:

- custom package versions
- post-install file changes (built-in md5 verification)
- checks if these customizations interfere with MU installation
- provides a list of packages for which there are updated versions available

# Supported MOS versions:
9.0, 9.1

# Prerequisites
- designed to run on Fuel node, if running from any other node, these
requirements should be met:

  1. python 2.6 or 2.7
  2. root access via public key to any node via Fuel admin network
  3. edit configuration file to specify Fuel's IP address instead of `127.0.0.1`

# Installation and updates
- install python-cudet: `pip install git+https://github.com/avgoor/python-cudet`
- To update already installed python-cudet use pip to reinstall the package:
  `pip uninstall python-cudet; pip install python-cudet`.

# Usage
- cudet takes two options from command-line "--env" which allows you to
  run the check against particular environment and "--node" which allows you
  to run the check against particular node
- make sure you are ok to IO load your nodes (root partition), since the tool
  will do md5 verification of each installed package on each node (cudet uses
  `nice` and `ionice` to minimize the impact)
- optionally copy and edit `/usr/share/cudet/cudet-config.yaml` - for example
  you can filter nodes by various parameters, then use `-c` option to specify
  your edited configuration file.
- run the tool - `cudet`
- optionally redirect output to a file: `cudet | tee results.yaml`
- you can regenerate the report any time without actually collecting data from
  nodes again (connection to Fuel still needed to initialize the array of
  nodes) - to do this specify `-f` (`--fake`) option - this will use data
  previously collected in `/tmp/cudet/info` folder (unless you or Cudet have
  erased it)
- data (except stdout which you have to capture manually) is collected into
  `/tmp/cudet/info` if you decide to use/share it

# Fuel extensions:
- The `fuel2 update` extension provides a convenient way to change metadata of
  an environment and start the re-deploy procedure to obtain an update
- The `fuel2 report` extension provides a filter for summary reports, which
  can be used to filter out unneeded items from a noop-run summary report
