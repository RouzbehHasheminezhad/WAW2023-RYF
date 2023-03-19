import argparse
import gzip
import os
import re
import shutil
import tarfile
import time
import warnings
import zipfile
import graph_tool.all as gt
import numpy as np
import pandas as pd
import rarfile
import requests
import scipy

global num_engines


def set_num_engines(n_engines):
    global num_engines
    if n_engines == -1:
        num_engines = os.cpu_count()
    else:
        num_engines = n_engines


def get_num_engines():
    global num_engines
    return num_engines


def process_map(func, args, desc):
    from tqdm.contrib.concurrent import process_map
    return process_map(func, args, desc=desc, max_workers=get_num_engines())


def listdir(addr):
    res = os.listdir(addr)
    try:
        res.remove(".DS_Store")
    except (Exception,):
        pass
    return res


def mkdir(addr, wipe=True):
    try:
        if os.path.exists(addr):
            if wipe:
                shutil.rmtree(addr)
                os.mkdir(addr)
            else:
                pass
        else:
            os.mkdir(addr)
    except (Exception,):
        pass


def decompress(args):
    read_addr, write_addr = args
    if read_addr.endswith(".tar.gz") or read_addr.endswith(".tar.bz2"):
        tar_f = tarfile.open(read_addr)
        tar_f.extractall(write_addr)
        tar_f.close()
    elif read_addr.endswith(".zip"):
        with zipfile.ZipFile(read_addr, "r") as zip_f:
            zip_f.extractall(write_addr)
    elif read_addr.endswith(".gz"):
        with gzip.open(read_addr, 'r') as gz_f:
            with open(write_addr + read_addr.split("/")[-1][:-len(".gz")], 'wb') as f_out:
                shutil.copyfileobj(gz_f, f_out)
    elif read_addr.endswith(".rar"):
        with rarfile.RarFile(read_addr, 'r') as archive:
            archive.extractall(path=write_addr)


def konect_to_gt(args):
    saving_name, konect_name = args
    g = gt.Graph(directed=False)
    prefix = "konect_decompressed/" + konect_name
    for postfix in listdir(prefix):
        if not postfix.startswith("out."):
            continue
        else:
            edges = np.loadtxt("konect_decompressed/" + konect_name + "/" + postfix, dtype=int, comments="%")
            edges[:, :2] -= 1
            g.add_edge_list(edges)
            g.save("konect/" + saving_name + ".gt", fmt="gt")


def transfer_edges(edges_list):
    index_map = {}
    index = 0
    edges = []
    for i in range(len(edges_list)):
        u, v = edges_list[i]
        if u not in index_map:
            index_map[u] = index
            index += 1
        if v not in index_map:
            index_map[v] = index
            index += 1
        edges.append((index_map[u], index_map[v]))
    return edges


def snap_to_gt(args):
    snap_name, cat, f_read_addr = args
    g = gt.Graph(directed=False)
    g.add_edge_list(transfer_edges(np.loadtxt(f_read_addr, dtype=int, delimiter=",", skiprows=1)))
    network, subnetwork = snap_name.split("/") if len(snap_name.split("/")) == 2 else [snap_name.split("/")[0]] * 2
    mkdir(os.getcwd() + "/snap/" + network, wipe=False)
    g.save(os.getcwd() + "/snap/" + network + "/" + subnetwork + ".gt", fmt="gt")
    return tuple(["SNAP", network, subnetwork, cat, os.getcwd() + "/snap/" + network + "/" + subnetwork + ".gt"])


def download(args):
    url, f_name = args
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with requests.get(url, stream=True, verify=False) as r:
            r.raise_for_status()
            with open(f_name, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)


def collect_konect(df_konect):
    addr_raw = os.getcwd() + "/konect_raw/"
    addr_decompressed = os.getcwd() + "/konect_decompressed/"
    addr_processed = os.getcwd() + "/konect/"

    mkdir(addr_raw)
    mkdir(addr_decompressed)
    mkdir(addr_processed)

    net_list = [(x.split("[")[-1].split("]")[0], x.split(" [")[0]) for x in df_konect["Name"].values]
    name_map = dict(net_list)
    url_list = ["http://konect.cc/files/download.tsv." + internal_name + ".tar.bz2" for (internal_name, _) in net_list]

    process_map(download, [(url, addr_raw + url.split("/")[-1][len("download.tsv."):]) for url in url_list],
                desc="collect_konect")
    process_map(decompress, [(addr_raw + f_name, addr_decompressed) for f_name in listdir(addr_raw)],
                desc="decompress_konect")
    process_map(konect_to_gt, [(name_map[f_name], f_name) for f_name in listdir(addr_decompressed)],
                desc="konect_to_gt")

    shutil.rmtree(addr_raw)
    shutil.rmtree(addr_decompressed)

    return [("KONECT", x.split(" [")[0], x.split(" [")[0], y, os.getcwd() + "/konect/" + x.split(" [")[0] + ".gt") for
            (x, y) in
            list(zip(df_konect["Name"], df_konect["Category"]))]


def netzschleuder_helper(arg):
    gt.collection.ns[arg[1] + "/" + arg[2] if arg[1] != arg[2] else arg[1]].save(arg[-1], fmt="gt")


def collect_netzschleuder(df_netzschleuder):
    addr_netzschleuder = os.getcwd() + "/netzschleuder/"
    mkdir(addr_netzschleuder)
    args = []
    for (x, y) in list(zip(df_netzschleuder["Name"], df_netzschleuder["Category"])):
        network, subnetwork = x.split("/") if len(x.split("/")) == 2 else [x.split("/")[0]] * 2
        net_addr = addr_netzschleuder + network + "/"
        mkdir(net_addr, wipe=False)
        args.append(("Netzschleuder", network, subnetwork, y, net_addr + subnetwork + ".gt"))

    process_map(netzschleuder_helper, args, desc="collect_netzschleuder")

    return args


def collect_snap(df_snap):
    name_cat_map = dict(zip(df_snap["Name"], df_snap["Category"]))
    addr_snap_raw = os.getcwd() + "/snap_raw/"
    addr_snap_decompressed = os.getcwd() + "/snap_decompressed/"
    addr_snap_processed = os.getcwd() + "/snap/"
    mkdir(addr_snap_raw)
    mkdir(addr_snap_decompressed)
    mkdir(addr_snap_processed)

    urls = ["https://snap.stanford.edu/data/git_web_ml.zip",
            "https://snap.stanford.edu/data/twitch.zip",
            "https://snap.stanford.edu/data/gemsec_deezer_dataset.tar.gz",
            ]

    process_map(download, [(url, addr_snap_raw + url.split("/")[-1]) for url in urls], desc="collect_snap")
    process_map(decompress, [(addr_snap_raw + url.split("/")[-1], addr_snap_decompressed) for url in urls],
                desc="decompress_snap")

    args = []
    for x in os.walk(os.getcwd() + "/snap_decompressed/"):
        if len(x[1]) == 0:
            name = x[0].removeprefix(os.getcwd() + "/snap_decompressed/")
            if name.startswith("twitch"):

                args.extend([("musae-twitch/" + name.split("/")[-1], x[0] + "/" + f_name) for f_name in x[2] if
                             f_name.endswith("edges.csv")])

            elif name.startswith("deezer"):
                args.extend([("gemsec-Deezer/" + f_name.split("_")[0], x[0] + "/" + f_name) for f_name in x[2] if
                             f_name.endswith("edges.csv")])
            else:
                args.extend([("musae-github", x[0] + "/" + f_name) for f_name in x[2] if f_name.endswith("edges.csv")])
    args = process_map(snap_to_gt, [(snap_name, name_cat_map[snap_name], addr_read) for (snap_name, addr_read) in args],
                       desc="snap_to_gt")
    shutil.rmtree(addr_snap_raw)
    shutil.rmtree(addr_snap_decompressed)
    return args


def icon_fb_to_gt(args):
    icon_name, addr_write, add_read = args
    A = scipy.io.loadmat(os.path.join(add_read))["A"].tocsr().astype(bool)
    sources, targets, _ = scipy.sparse.find(A)
    g = gt.Graph(directed=False)
    g.add_vertex(A.shape[0])
    g.add_edge_list([(sources[j], targets[j]) for j in range(len(sources))])
    g.save(addr_write)
    return tuple(["ICON", "Facebook100", icon_name, "Social", addr_write])


def collect_fb(addr_icon, args_fb):
    raw_dir, decompressed_dir, write_dir = addr_icon + "fb_raw/", addr_icon + "fb_decompressed/", addr_icon + "Facebook100/"
    mkdir(raw_dir)
    mkdir(decompressed_dir)
    mkdir(write_dir)
    download(("https://archive.org/download/oxford-2005-facebook-matrix/facebook100.zip", raw_dir + "facebook.zip"))
    decompress((raw_dir + "facebook.zip", decompressed_dir))
    args = [(arg, addr_icon + "Facebook100/" + arg + ".gt",
             decompressed_dir + "facebook100/" + (arg if arg != "Wash U32" else "WashU32") + ".mat") for arg in args_fb]
    args = process_map(icon_fb_to_gt, args, desc="icon_Facebook100")

    shutil.rmtree(raw_dir)
    shutil.rmtree(decompressed_dir)
    return args


def find_skip(file_path):
    file = open(file_path)
    skip = 0
    footer = 0
    edges = True
    triangles = False
    for line in file.read().splitlines():
        if edges:
            skip = skip + 1
        if line[:len("*Edges")] == "*Edges":
            edges = False
        if line[:len("*Triangles")] == "*Triangles":
            triangles = True
        if triangles:
            footer = footer + 1

    return [skip, footer]


def icon_rest_to_gt(args):
    addr_icon, icon_name, read_path, category, network, subnetwork = args

    g = gt.Graph(directed=False)

    if icon_name.startswith("AMiner"):
        skip_header, skip_footer = find_skip(read_path)
        g.add_edge_list(transfer_edges(
            np.genfromtxt(read_path, usecols=[0, 1], skip_header=skip_header, skip_footer=skip_footer, dtype=int)))
    elif icon_name.startswith("India"):
        skip_header, skip_footer = find_skip(read_path)
        g.add_edge_list(
            transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], skip_header=1, skip_footer=skip_footer, dtype=str)))
    elif icon_name.startswith("PGP"):
        skip_header, skip_footer = find_skip(read_path)
        g.add_edge_list(
            transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], skip_header=skip_header, skip_footer=0, dtype=int)))
    elif icon_name.startswith("S. cerevisiae"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], dtype=str)))
    elif icon_name.startswith("WHOIS"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], dtype=int)))
    elif icon_name.startswith("Flickr"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], skip_header=4, dtype=int)))
    elif icon_name.startswith("Binary"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], dtype=str)))
    elif icon_name.startswith("Reguly"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], dtype=str)))
    elif icon_name.startswith("UK"):
        g.add_edge_list(transfer_edges(np.genfromtxt(read_path, usecols=[0, 1], dtype=str)))
    elif icon_name.startswith("Myocardial"):
        df = pd.DataFrame(pd.read_excel(read_path, sheet_name="My-Inflamome", header=None))
        df.columns = ["source", "type", "target"]
        g.add_edge_list(transfer_edges(list(zip(df["source"], df["target"]))))
    elif icon_name.startswith("Yeast"):
        with open(read_path, 'r') as f:
            g.add_edge_list(transfer_edges([(x.strip().split()) for x in
                                            re.search(r'Edges\n.*?Edges', f.read(), re.DOTALL).group().split("\n")[
                                            1:-1]]))
    g.save(addr_icon + network + "/" + subnetwork + ".gt", fmt="gt")
    return tuple(["ICON", network, subnetwork, category, addr_icon + network + "/" + subnetwork + ".gt"])


def icon_helper(args):
    net_url_map = {
        "AMiner scientific collaborations (2009)/AMiner DatabaseSys sub0 coauthors": (
            "https://www.aminer.org/lab-datasets/soinf/graphs_authors.rar", "graph-T24_sub0.net"),
        "PGP web of trust (2004)": ("http://deim.urv.cat/~alexandre.arenas/data/xarxes/PGP.zip", "PGPgiantcompo.net"),
        "WHOIS AS Internet (2006)": (
            "https://www.caida.org/catalog/papers/2005_tr_2005_02/supplemental/data_sources/WHOIS.gz", "WHOIS"),
        "Flickr (2012)": ("http://snap.stanford.edu/data/flickrEdges.txt.gz", "flickrEdges.txt"),
        "Yeast interactome (2003)": ("http://vlado.fmf.uni-lj.si/pub/networks/data/bio/Yeast/yeast.zip", "Yeast.paj"),
        "Myocardial inflammation proteins (2011)": (
            "https://static-content.springer.com/esm/art%3A10.1186%2F1755-8794-4-59/MediaObjects/12920_2011_252_MOESM1_ESM.XLS",),
        "Binary interactomes (various species; 2012)/A. thaliana (mustard)": (
            "http://hint.yulab.org/old_versions/Before_2019/ArabidopsisThaliana_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/C. elegans (nematode)": (
            "http://hint.yulab.org/old_versions/Before_2019/CaenorhabditisElegans_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/D. melanogaster (fly)": (
            "http://hint.yulab.org/old_versions/Before_2019/DrosophilaMelanogaster_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/E. coli K12": (
            "http://hint.yulab.org/old_versions/Before_2019/EscherichiaColiK12_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/H. sapiens (human)": (
            "http://hint.yulab.org/old_versions/Before_2019/HomoSapiens_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/M. musculus (mouse)": (
            "http://hint.yulab.org/old_versions/Before_2019/MusMusculus_binary_hq.txt",),
        "Binary interactomes (various species; 2012)/S. cerevisiae S288C (budding yeast)": (
            "http://hint.yulab.org/old_versions/Before_2019/SaccharomycesCerevisiaeS288C_binary_hq.txt",),
        "Reguly yeast interactome (2006)": (
            "http://interactome.dfci.harvard.edu/S_cerevisiae/download/LC_multiple.txt",),
        "S. cerevisiae interactome (2008)": ("http://math.bu.edu/people/kolaczyk/datasets/ppi.zip", "ppi.txt"),
        "India bus routes (2016)/India_bus_HBN_Hyderabad_2016": (
            "https://github.com/achatterjee3/Dataset/raw/master/Bus%20data.rar", "Bus data/hbn.txt"),
        "India bus routes (2016)/India_bus_ABN_Ahmedabad_2016": (
            "https://github.com/achatterjee3/Dataset/raw/master/Bus%20data.rar", "Bus data/abn.txt"),
        "India bus routes (2016)/India_bus_CBN_Chennai_2016": (
            "https://github.com/achatterjee3/Dataset/raw/master/Bus%20data.rar", "Bus data/cbn.txt"),
        "India bus routes (2016)/India_bus_DBN_Delhi_2016": (
            "https://github.com/achatterjee3/Dataset/raw/master/Bus%20data.rar", "Bus data/dbn.txt"),
        "UK public transportation (2004-2011)/edges_rail": (
            "https://bitbucket.org/deregtr/gb_ptn/raw/3475dfefd4a85ec4bd4cb92df34153e84b52eaa4/edges_rail.dat",)
    }
    to_convert_args = []
    for (addr_icon, addr_icon_raw, x, category) in args:
        network, subnetwork = x.split("/") if len(x.split("/")) == 2 else [x.split("/")[0]] * 2
        mkdir(addr_icon + network, wipe=False)
        f_name = addr_icon_raw + net_url_map[x][0].split("/")[-1]
        download((net_url_map[x][0], f_name))
        if len(net_url_map[x]) > 1:
            try:
                decompress((f_name, addr_icon_raw))
                os.remove(f_name)
            except (Exception,):
                pass
            to_convert_args.append((addr_icon, x, addr_icon_raw + net_url_map[x][1], category, network, subnetwork))

        else:
            to_convert_args.append(
                (addr_icon, x, addr_icon_raw + net_url_map[x][0].split("/")[-1], category, network, subnetwork))

    return process_map(icon_rest_to_gt, to_convert_args, desc="icon_rest")


def collect_icon(df_icon):
    addr_icon = os.getcwd() + "/icon/"
    addr_icon_raw = addr_icon + "raw/"
    mkdir(addr_icon)
    mkdir(addr_icon_raw)
    args_fb = []
    args_etc = []
    for (x, y) in list(zip(df_icon["Name"], df_icon["Category"])):
        if not x.startswith("Facebook100"):
            args_etc.append((addr_icon, addr_icon_raw, x, y))
        else:
            args_fb.append(x.split("/")[1])
    args = collect_fb(addr_icon, args_fb)
    args.extend(icon_helper(args_etc))
    shutil.rmtree(addr_icon_raw)
    return args


def run_collection():
    df = pd.read_csv("networks_spreadsheet.csv", delimiter=";")
    collected = []
    collected.extend(collect_konect(df.loc[df["Source"] == "KONECT"]))
    collected.extend(collect_netzschleuder(df.loc[df["Source"] == "Netzschleuder"]))
    collected.extend(collect_snap(df.loc[df["Source"] == "SNAP"]))
    collected.extend(collect_icon(df.loc[df["Source"] == "ICON"]))
    return collected


def process(args):
    dataset_dir, source, network, subnetwork, category, read_addr = args
    mkdir(dataset_dir + category, wipe=False)
    mkdir(dataset_dir + category + "/" + network, wipe=False)
    mkdir(dataset_dir + category + "/" + network + "/" + subnetwork, wipe=False)
    mkdir(dataset_dir + category + "/" + network + "/" + subnetwork + "/Graph-Data", wipe=False)
    mkdir(dataset_dir + category + "/" + network + "/" + subnetwork + "/Robustness-Score-Data", wipe=False)
    mkdir(dataset_dir + category + "/" + network + "/" + subnetwork + "/Scalefreeness-Score-Data", wipe=False)

    g = gt.load_graph(read_addr)
    source = g.new_graph_property("string")
    source[g] = source
    g.graph_properties["source"] = source
    g.save(dataset_dir + category + "/" + network + "/" + subnetwork + "/Graph-Data/" + subnetwork + ".gt", fmt="gt")


def prepare_dataset(args):
    dataset_dir = os.getcwd() + "/dataset/"
    mkdir(dataset_dir)
    process_map(process, [(dataset_dir,) + arg for arg in args], desc="preparing dataset")
    shutil.rmtree(os.getcwd() + "/icon/")
    shutil.rmtree(os.getcwd() + "/konect/")
    shutil.rmtree(os.getcwd() + "/snap/")
    shutil.rmtree(os.getcwd() + "/netzschleuder/")


def argument_checker(x):
    num = int(x)
    if num < 0 and num != -1:
        raise argparse.ArgumentTypeError('invalid value!')
    else:
        return num


if __name__ == '__main__':
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('--cores', type=argument_checker, required=True)
    cli_input = parser.parse_args()
    set_num_engines(cli_input.cores)
    prepare_dataset(run_collection())
    print("Total dataset compilation time (in seconds): " + str(time.time() - start))