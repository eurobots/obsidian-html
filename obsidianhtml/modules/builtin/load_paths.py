from ..base_classes import ObsidianHtmlModule
from ...lib import FindVaultByEntrypoint

import yaml
from pathlib import Path


class LoadPathsModule(ObsidianHtmlModule):
    """
    Based on the config.yml we can determine paths of relevance, such as the html output folder. These paths will be put in paths.yml
    Paths are all encoded as posix strings. Paths are absolute unless prefixed with _rel
    """

    @property
    def requires(self):
        return tuple(["config.yml"])

    @property
    def provides(self):
        return tuple(["paths.json"])

    @property
    def alters(self):
        return tuple()

    def set_obsidian_folder_path_str(self):
        if self.gc("toggles/compile_md") is False:  # don't check vault if we are compiling directly from markdown to html
            return

        # Use user provided obsidian_folder_path_str
        if "obsidian_folder_path_str" in self.config and self.config["obsidian_folder_path_str"] != "<DEPRECATED>":
            result = FindVaultByEntrypoint(self.config["obsidian_folder_path_str"])
            if result:
                if Path(result) != Path(self.config["obsidian_folder_path_str"]).resolve():
                    print(f"Error: The configured obsidian_folder_path_str is not the vault root. Change its value to {result}")
                    exit(1)
                return result
            else:
                print("ERROR: Obsidianhtml could not find a valid vault. (Tip: obsidianhtml looks for the .obsidian folder)")
                exit(1)
            return result

        # Determine obsidian_folder_path_str from obsidian_entrypoint_path_str
        result = FindVaultByEntrypoint(self.config["obsidian_entrypoint_path_str"])
        if result:
            return result
        else:
            print(
                f"ERROR: Obsidian vault not found based on entrypoint {self.config['obsidian_entrypoint_path_str']}.\n\tDid you provide a note that is in a valid vault? (Tip: obsidianhtml looks for the .obsidian folder)"
            )
            exit(1)

    def run(self):
        gc = self.gc

        self.set_obsidian_folder_path_str()

        paths = {
            "obsidian_folder": Path(self.set_obsidian_folder_path_str()),
            "md_folder": Path(gc("md_folder_path_str")).resolve(),
            "obsidian_entrypoint": Path(gc("obsidian_entrypoint_path_str")).resolve(),
            "md_entrypoint": Path(gc("md_entrypoint_path_str")).resolve(),
            "html_output_folder": Path(gc("html_output_folder_path_str")).resolve(),
        }
        paths["original_obsidian_folder"] = paths["obsidian_folder"]  # use only for lookups!
        paths["dataview_export_folder"] = paths["obsidian_folder"].joinpath(gc("toggles/features/dataview/folder"))

        if gc("toggles/extended_logging", cached=True):
            paths["log_output_folder"] = Path(gc("log_output_folder_path_str")).resolve()

        # Deduce relative paths
        if gc("toggles/compile_md", cached=True):
            paths["rel_obsidian_entrypoint"] = paths["obsidian_entrypoint"].relative_to(paths["obsidian_folder"])
        paths["rel_md_entrypoint_path"] = paths["md_entrypoint"].relative_to(paths["md_folder"])

        # Convert to posix string for exporting
        for key in paths.keys():
            paths[key] = paths[key].as_posix()

        # Export
        self.write("paths.json", paths, asjson=True)

    def integrate_load(self, pb):
        """Used to integrate a module with the current flow, to become deprecated when all elements use modular structure"""
        self._integrate_ensure_module_data_folder()
        self.write("config.yml", yaml.dump(pb.config.config))

    def integrate_save(self, pb):
        """Used to integrate a module with the current flow, to become deprecated when all elements use modular structure"""
        pb.paths = self.read("paths.json", asjson=True)
        for key in pb.paths:
            pb.paths[key] = Path(pb.paths[key])
