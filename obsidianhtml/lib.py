import os                   #
import re                   # regex string finding/replacing
import yaml
import frontmatter          # remove yaml frontmatter from md files
import warnings
import shutil               # used to remove a non-empty directory, copy files
import tempfile             # used to create temporary files/folders
import time
import unicodedata
import glob

import urllib.parse         # convert link characters like %

from pathlib import Path    # 
from string import ascii_letters, digits
from functools import cache
from subprocess import Popen, PIPE
from appdirs import AppDirs

# Open source files in the package
import importlib.resources as pkg_resources
import importlib.util

from . import src 
 
class DuplicateFileNameInRoot(Exception):
    pass
class MalformedTags(Exception):
    pass

def print_global_help_and_exit(exitCode:int):
    print()
    version = OpenIncludedFile('version')
    print(OpenIncludedFile('help_texts/help_text').replace('{version}', version))
    exit(exitCode)

def get_obshtml_appdir_folder_path():
    return Path(AppDirs("obsidianhtml", "obsidianhtml").user_config_dir)

def get_default_appdir_config_yaml_path():
    appdir_config_folder_path = get_obshtml_appdir_folder_path()
    return appdir_config_folder_path.joinpath('config.yml')

def WriteFileLog(files, log_file_name, include_processed=False):
    if include_processed:
        s = "| key | processed note? | processed md? | note | markdown | html | html link relative | html link absolute |\n|:---|:---|:---|:---|:---|:---|:---|:---|\n"
    else:
        s = "| key | note | markdown | html | html link relative | html link absolute |\n|:---|:---|:---|:---|:---|:---|\n"

    for k in files.keys():
        fo = files[k]
        n = ''
        m = ''
        h = ''
        if 'note' in fo.path.keys():
            n = fo.path['note']['file_absolute_path']
        if 'markdown' in fo.path.keys():
            m = fo.path['markdown']['file_absolute_path']
        if 'html' in fo.path.keys():
            # temp
            fo.get_link('html')
            h = fo.path['html']['file_absolute_path']
        if 'html' in fo.link.keys():
            hla = fo.link['html']['absolute']
            hlr = fo.link['html']['relative']

        if include_processed:
            s += f"| {k} | {fo.processed_ntm} | {fo.processed_mth} | {n} | {m} | {h} | {hlr} | {hla} |\n"
        else:
            s += f"| {k} | {n} | {m} | {h} | {hlr} | {hla} |\n"

    with open(log_file_name, 'w', encoding='utf-8') as f:
        f.write(s)

def simpleHash(text:str):
    hash=0
    for ch in text:
        hash = ( hash*281  ^ ord(ch)*997) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    return str(hash)


def ConvertTitleToMarkdownId(title):
    # remove whitespace and lowercase
    idstr = title.lower().strip()

    # remove special characters "hi-hello-'bye!'" --> "hi-hello-bye"
    idstr = "".join([ch for ch in idstr if ch in (ascii_letters + digits + ' -_')])

    # convert "hi hello - 'bye!'" --> "hi-hello---'bye!'" --> "hi-hello-'bye!'"
    idstr = idstr.replace(' ', '-')
    while '--' in idstr:
        idstr = idstr.replace('--', '-')

    return idstr

def slugify(value, separator='-', unicode=False):
    """ Slugify a string, to make it URL friendly. """
    if not unicode:
        # Replace Extended Latin characters with ASCII, i.e. žlutý → zluty
        value = unicodedata.normalize('NFKD', value)
        value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', ' ', value).strip().lower()
    return re.sub(r'[{}\s]+'.format(separator), separator, value)


@cache
def GetIncludedResourcePath(resource):
    path = importlib.util.find_spec("obsidianhtml.src").submodule_search_locations[0]
    return Path(os.path.join(path, resource))

@cache
def OpenIncludedFile(resource):
    path = GetIncludedResourcePath(resource)
    with open(path, 'r', encoding="utf-8") as f:
        return f.read()

def GetIncludedFilePaths(subpath=''):
    path = importlib.util.find_spec("obsidianhtml.src").submodule_search_locations[0]
    path = os.path.join(path, subpath)
    onlyfiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    return onlyfiles

@cache
def OpenIncludedFileBinary(resource):
    path = GetIncludedResourcePath(resource)
    with open(path, 'rb') as f:
        return f.read()    

@cache
def CreateStaticFilesFolders(html_output_folder):
    obsfolder = html_output_folder.joinpath('obs.html')
    os.makedirs(obsfolder, exist_ok=True)

    static_folder = obsfolder.joinpath('static')
    os.makedirs(static_folder, exist_ok=True)

    data_folder = obsfolder.joinpath('data')
    os.makedirs(data_folder, exist_ok=True)

    rss_folder = obsfolder.joinpath('rss')
    os.makedirs(rss_folder, exist_ok=True)

    return (obsfolder, static_folder, data_folder, rss_folder)

def ExportStaticFiles(pb):
    (obsfolder, static_folder, data_folder, rss_folder) = CreateStaticFilesFolders(pb.paths['html_output_folder'])

    # define files to be copied over (standard copy, static_folder)
    copy_file_list = [
        ['svgs/external.svg', 'external.svg'],
        ['svgs/hashtag.svg', 'hashtag.svg'],
        ['html/css/taglist.css', 'taglist.css'],
        ['rss/rss.svg', 'rss.svg'],
        ['index_from_dir_structure/dirtree.svg', 'dirtree.svg'],
        ['js/obsidian_core.js', 'obsidian_core.js'],
        ['js/encoding.js', 'encoding.js'],
        ['index_from_dir_structure/dirtree.js', 'dirtree.js']
    ]

    css_files_list = [
        ['html/css/global_main.css', 'global_main.css']
    ]

    if pb.config.feature_is_enabled('graph', cached=True):
        copy_file_list.append(['imported/3d-force-graph.v1.70.10.min.js', '3d-force-graph.js'])
        css_files_list.append(['graph/graph.css', 'graph.css'])
        copy_file_list.append(['graph/graph.svg', 'graph.svg'])
        #copy_file_list.append(['graph/default_grapher_2d.js', 'default_grapher_2d.js'])
        #copy_file_list.append(['graph/default_grapher_3d.js', 'default_grapher_3d.js'])

    if pb.config.feature_is_enabled('mermaid_diagrams', cached=True):
        copy_file_list.append(['imported/mermaid.9.0.1.min.js', 'mermaid.9.0.1.min.js'])
        copy_file_list.append(['imported/mermaid.9.0.1.min.js.map', 'mermaid.9.0.1.min.js.map'])
        copy_file_list.append(['html/css/mermaid.css', 'mermaid.css'])

    if pb.config.feature_is_enabled('code_highlight', cached=True):
        css_files_list.append(['html/css/codehilite.css', 'codehilite.css'])

    if pb.config.feature_is_enabled('search', cached=True):
        copy_file_list.append(['search/search.svg', 'search.svg'])
        copy_file_list.append(['search/pako.js', 'pako.js'])
        copy_file_list.append(['search/search.js', 'search.js'])
        css_files_list.append(['search/search.css', 'search.css'])
        copy_file_list.append(['imported/flexsearch.v0.7.2.bundle.js', 'flexsearch.bundle.js'])

    # if pb.config.feature_is_enabled('math_latex', cached=True):
    #     copy_file_list.append(['latex/load_mathjax.js', 'load_mathjax.js'])
    #     copy_file_list.append(['imported/mathjax.v3.es5.tex-chtml.js', 'tex-chtml.js'])

    if pb.config.feature_is_enabled('callouts', cached=True):
        css_files_list.append(['html/css/callouts.css', 'callouts.css'])

    if pb.gc('toggles/features/styling/layout', cached=True) == 'documentation':
        copy_file_list.append(['js/load_dirtree_footer.js', 'load_dirtree_footer.js'])

    if pb.gc('toggles/features/styling/layout', cached=True) == 'tabs':
        copy_file_list.append(['js/obsidian_tabs_footer.js', 'obsidian_tabs_footer.js'])

    # create master.css file
    css_files_list += [
        [f'html/layouts/{pb.gc("_css_file")}', 'main.css'],
        ['html/themes/theme-obsidian.css', 'theme-obsidian.css'],
        ['html/css/global_overwrites.css', 'global_overwrites.css']
    ]
    css = ''
    for filepath, _ in css_files_list:
        css += '\n\n' + OpenIncludedFile(filepath)
    
    copy_file_list.append([{'type': 'contents', 'contents': css}, 'master.css'])

    # copy static files over to the static folder
    for file in copy_file_list:
        file_record = file[0]
        file_name = file[1]
        contents = ''

        # Get file contents
        if isinstance(file_record, dict):
            # ... from absolute path
            if file_record['type'] == 'absolute_path_str':
                with open(file_record['path'], 'r', encoding='utf-8') as f:
                    contents = f.read()
            # ... from file_record itself
            elif file_record['type'] == 'contents':
                contents = file_record['contents'] 
            else:
                raise Exception('ERROR: file_record type in unknown')
        else:
            # ... from package
            contents = OpenIncludedFile(file_record)

        # Define dest path and html_url_prefix
        dst_path = static_folder.joinpath(file_name)
        html_url_prefix = get_html_url_prefix(pb, abs_path_str=dst_path)
        
        # Set pane divs
        toc_pane_div = "right_pane_content"
        content_pane_div = "left_pane_content"
        if pb.gc('toggles/features/styling/layout') == 'documentation' and pb.gc('toggles/features/styling/flip_panes'):
            toc_pane_div = "left_pane_content"
            content_pane_div = "right_pane_content"

        # Templating
        if file_name in ('master.css', 'main.css', 'global_main.css', 
                            'obsidian_core.js', 
                            'search.js', 'search.css'):

            url_mode = 'absolute'
            if pb.gc('toggles/relative_path_html'):
                url_mode = 'relative'

            contents = contents.replace('{html_url_prefix}', html_url_prefix)\
                 .replace('{configured_html_url_prefix}', pb.configured_html_prefix)\
                 .replace('{no_tabs}',str(int(pb.gc('toggles/no_tabs', cached=True))))\
                 .replace('{relative_paths}', str(int(pb.gc('toggles/relative_path_html'))))\
                 .replace('{documentation_mode}',str(int(pb.gc('toggles/features/styling/layout')=='documentation')))\
                 .replace('{toc_pane}',str(int(pb.gc('toggles/features/styling/toc_pane'))))\
                 .replace('{mermaid_enabled}',str(int(pb.gc('toggles/features/mermaid_diagrams/enabled'))))\
                 .replace('{toc_pane_div}', toc_pane_div)\
                 .replace('{content_pane_div}', content_pane_div)\
                 .replace('{gzip_hash}', pb.gzip_hash)\
                 .replace('{url_mode}', url_mode)\

            contents = contents.replace('__accent_color__', pb.gc('toggles/features/styling/accent_color', cached=True))\
                 .replace('__loading_bg_color__', pb.gc('toggles/features/styling/loading_bg_color', cached=True))\
                 .replace('__max_note_width__', pb.gc('toggles/features/styling/max_note_width', cached=True))\

        # Write to dest
        with open (dst_path, 'w', encoding="utf-8") as f:
            f.write(contents)

    # copy binary files to dst (byte copy, static_folder)
    copy_file_list_byte = [
        ['html/fonts/SourceCodePro-Regular.ttf', 'SourceCodePro-Regular.ttf'],
        ['html/fonts/Roboto-Regular.ttf', 'Roboto-Regular.ttf']
    ]
    for file_name in copy_file_list_byte:
        c = OpenIncludedFileBinary(file_name[0])
        with open (static_folder.joinpath(file_name[1]), 'wb') as f:
            f.write(c)

    # Custom copy
    c = OpenIncludedFile('html/templates/not_created.html')
    dst_path = pb.paths['html_output_folder'].joinpath('not_created.html')
    html_url_prefix = get_html_url_prefix(pb, abs_path_str=dst_path)

    with open (dst_path, 'w', encoding="utf-8") as f:
        html = PopulateTemplate(pb, 'none', pb.dynamic_inclusions, pb.html_template, content=c, dynamic_includes='')
        html = html.replace('{html_url_prefix}', html_url_prefix).replace('{left_pane_content}', '').replace('{right_pane_content}', '')
        f.write(html)

    c = OpenIncludedFileBinary('html/favicon.ico')
    with open (pb.paths['html_output_folder'].joinpath('favicon.ico'), 'wb') as f:
        f.write(c)


    if pb.gc('toggles/features/graph/enabled', cached=True):
        # create grapher files
        dynamic_imports = '// DYNAMIC\n' + ('/'*79) + '\n'
        grapher_list = []
        grapher_hash = []

        graph_folder = static_folder.joinpath('graphers/')
        graph_folder.mkdir(parents=True, exist_ok=True) 

        for grapher in pb.graphers:
            # save file in graphers folder
            dst_path = graph_folder.joinpath(f'{grapher["id"]}.js')
            with open (dst_path, 'w', encoding="utf-8") as f:
                f.write(grapher["contents"])
            
            # add to dynamic imports in grapher.js
            dynamic_imports += f"import * as grapher_{grapher['id']} from './graphers/{grapher['id']}.js';\n"

            # add to grapher list
            grapher_list.append("{'id': '" + grapher['id'] + "', 'name': '" + grapher['name'] + "', 'module': grapher_" + grapher['id'] + "}")
            grapher_hash.append("'" + grapher['id'] + "': " + grapher_list[-1])
        
        dynamic_imports += '\n'
        dynamic_imports += f"const CONFIGURED_HTML_URL_PREFIX = '{pb.configured_html_prefix}';\n"
        if pb.gc('toggles/relative_path_html'):
            dynamic_imports += 'const URL_MODE = "relative";\n'
        else:
            dynamic_imports += 'const URL_MODE = "absolute";\n'
        dynamic_imports += '\n'

        grapher_list = 'var graphers = [\n\t' + ',\n\t'.join(grapher_list) + '\n]\n'
        grapher_hash = 'var graphers_hash = {\n\t' + ',\n\t'.join(grapher_hash) + '\n}\n'

        # create graph.js
        dst_path = static_folder.joinpath('graph.js')
        html_url_prefix = get_html_url_prefix(pb, abs_path_str=dst_path)

        graph_js= OpenIncludedFile('graph/graph.js')
        graph_js = graph_js.replace('{html_url_prefix}', html_url_prefix)\
                           .replace('{coalesce_force}', pb.gc('toggles/features/graph/coalesce_force', cached=True))\
                           .replace('{no_tabs}',str(int(pb.gc('toggles/no_tabs', cached=True)))) 
        graph_js = dynamic_imports + grapher_list + grapher_hash + graph_js

        with open (dst_path, 'w', encoding="utf-8") as f:
            f.write(graph_js)


def PopulateTemplate(pb, node_id, dynamic_inclusions, template, content, html_url_prefix=None, title='', dynamic_includes=None, container_wrapper_class_list=None):
    # Cache
    if html_url_prefix is None:
        html_url_prefix = pb.gc("html_url_prefix")

    # Header inclusions
    dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/obsidian_core.js"></script>' + "\n"
    dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/encoding.js"></script>' + "\n"
    dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/master.css" />' + "\n"
    
    if pb.config.feature_is_enabled('callouts', cached=True):
        pass
        #dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/callouts.css" />' + "\n"

    if pb.config.feature_is_enabled('graph', cached=True):
        pass
        #dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/graph.css" />' + "\n"

    #if pb.config.feature_is_enabled('code_highlight', cached=True):
        #dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/codehilite.css" />' + "\n"

    if pb.config.feature_is_enabled('mermaid_diagrams', cached=True):
        dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/mermaid.9.0.1.min.js"></script>' + "\n"
        #dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/mermaid.css" />' + "\n"

    if pb.config.feature_is_enabled('math_latex', cached=True):
        #dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/tex-chtml.js"></script>' + "\n"
        #dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/load_mathjax.js"></script>' + "\n"
        dynamic_inclusions += OpenIncludedFile('latex/load_mathjax_header_template.html') + "\n"
        #dynamic_inclusions += '<script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>' + "\n"

    if pb.config.feature_is_enabled('search', cached=True):
        dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/flexsearch.bundle.js"></script>' + "\n"
        dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/pako.js"></script>' + "\n"
        dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/search.js"></script>' + "\n"
        #dynamic_inclusions += '<link rel="stylesheet" href="'+html_url_prefix+'/obs.html/static/search.css" />' + "\n"

    if pb.config.capabilities_needed['directory_tree']:
        dynamic_inclusions += '<script src="'+html_url_prefix+'/obs.html/static/dirtree.js"></script>' + "\n"
    
    if dynamic_includes is not None:
        dynamic_inclusions += dynamic_includes

    # Footer Inclusions
    footer_js_inclusions = ''
    
    if pb.gc('toggles/features/styling/layout', cached=True) == 'documentation':
        footer_js_inclusions += f'<script src="{html_url_prefix}/obs.html/static/load_dirtree_footer.js" type="text/javascript"></script>' + "\n"

    if pb.gc('toggles/features/styling/layout', cached=True) == 'tabs':
        footer_js_inclusions += f'<script src="{html_url_prefix}/obs.html/static/obsidian_tabs_footer.js" type="text/javascript"></script>' + "\n"

    # Include toggled components
    if pb.config.ShowIcon('rss'):
        code = OpenIncludedFile('rss/button_template.html')
        template = template.replace('{rss_button}', code)
    else:
        template = template.replace('{rss_button}', '')

    if pb.config.ShowIcon('graph'):
        code = OpenIncludedFile('graph/button_template.html')
        template = template.replace('{graph_button}', code)
    else:
        template = template.replace('{graph_button}', '')

    if pb.config.ShowIcon('search'):
        code = OpenIncludedFile('search/button_template.html')
        template = template.replace('{search_button}', code)
    else:
        template = template.replace('{search_button}', '')

    if pb.config.ShowIcon('tags_page'):
        code = OpenIncludedFile('tags_page/button_template.html')
        template = template.replace('{tags_page_button}', code)
    else:
        template = template.replace('{tags_page_button}', '')

    if pb.config.ShowIcon('theme_picker'):
        code = OpenIncludedFile('html/themes/button_template.html')
        template = template.replace('{theme_button}', code)
        code = OpenIncludedFile('html/themes/popup.html')
        template = template.replace('{theme_popup}', code)
    else:
        template = template.replace('{theme_button}', '')
        template = template.replace('{theme_popup}', '')

    if pb.config.ShowIcon('create_index_from_dir_structure'):
        output_path = html_url_prefix + '/' + pb.gc('toggles/features/create_index_from_dir_structure/rel_output_path', cached=True)
        code = OpenIncludedFile('index_from_dir_structure/button_template.html')
        code = code.replace('{dirtree_index_path}', output_path)
        template = template.replace('{dirtree_button}', code)
    else:
        template = template.replace('{dirtree_button}', '')

    if pb.config.feature_is_enabled('search', cached=True):
        template = template.replace('{search_html}', OpenIncludedFile('search/search.html'))
    else:
        template = template.replace('{search_html}', '')

    if pb.config.feature_is_enabled('search', cached=True):
        template = template.replace('{search_html}', OpenIncludedFile('search/search.html'))
    else:
        template = template.replace('{search_html}', '')

    # Misc
    if title == '':
        title = pb.gc('site_name', cached=True)

    if container_wrapper_class_list is None:
        container_wrapper_class_list = []
    if pb.gc('toggles/no_tabs', cached=True):
        container_wrapper_class_list.append('single_tab_page')    


    # Replace placeholders
    template = template\
        .replace('{node_id}', node_id)\
        .replace('{title}', title)\
        .replace('{dynamic_includes}', dynamic_inclusions)\
        .replace('{dynamic_footer_includes}', pb.dynamic_footer_inclusions)\
        .replace('{footer_js_inclusions}', footer_js_inclusions)\
        .replace('{html_url_prefix}', html_url_prefix)\
        .replace('{configured_html_url_prefix}', pb.configured_html_prefix)\
        .replace('{container_wrapper_class_list}', ' '.join(container_wrapper_class_list))\
        .replace('{no_tabs}', str(int(pb.gc('toggles/no_tabs', cached=True))))\
        .replace('{pinnedNode}', node_id)\
        .replace('{{navbar_links}}', '\n'.join(pb.navbar_links))\
        .replace('{content}', content)

    return template
        # Adding value replacement in content should be done in crawl_markdown_notes_and_convert_to_html, 
        # Between the md.StripCodeSections() and md.RestoreCodeSections() statements, otherwise codeblocks can be altered.
        

def is_installed(command):
    try:
        p = Popen([command], stdout=PIPE, stderr=PIPE)
        output, error = p.communicate()
    except FileNotFoundError as ex:
        return False
    return True

def should_ignore(ignore, path):
    if ignore is None:
        return False

    for ignore_path in [Path(x).resolve() for x in ignore]:
        if ignore_path.as_posix() == path.as_posix():
            return True
        if ignore_path.is_dir() and path.is_relative_to(ignore_path):
            return True

    return False


class YamlIndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(YamlIndentDumper, self).increase_indent(flow, False)

def pushd(path):
    cwd = os.getcwd()
    os.chdir(path)
    return cwd

def fetch_str(command):
    if isinstance(command, str):
        command = command.split(' ')
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()

    return output.decode('ascii').replace('\\n', '\n').strip()

def FindVaultByEntrypoint(entrypoint_path):
    vault_found = False

    # Allow both folders and entrypoint notes to be passed in
    search_folder = Path(entrypoint_path)
    if not search_folder.is_dir():
        search_folder = search_folder.parent

    history = search_folder.as_posix()
    while not vault_found: 
        try:
            history += '\n' + search_folder.as_posix()
            if search_folder.as_posix() == '/':
                print(history)
                return False
            for folder in [ f for f in os.scandir(search_folder) if f.is_dir(follow_symlinks=False) ]:
                if (folder.name == '.obsidian'):
                    return search_folder.resolve().as_posix()
            search_folder = search_folder.parent
        except Exception as ex:
            print(ex)
            return False
    return False

def get_rel_html_url_prefix(rel_path):
    depth = rel_path.count('/')
    if depth > 0:
        prefix = ('../'*depth)[:-1]
    else:
        prefix = '.'
    return prefix

def get_html_url_prefix(pb, rel_path_str=None, abs_path_str=None):
    # check input and convert rel_path_str from abs_path_str if necessary
    if rel_path_str is None:
        if abs_path_str is None:
            raise Exception("pass in either rel_path_str or abs_path_str")
        rel_path_str = Path(abs_path_str).relative_to(pb.paths['html_output_folder']).as_posix()

    # return html_prefix
    if pb.gc('toggles/relative_path_html', cached=True):
        html_url_prefix = pb.sc(path='html_url_prefix', value=get_rel_html_url_prefix(rel_path_str))
    else:
        html_url_prefix = pb.gc('html_url_prefix')
    return html_url_prefix