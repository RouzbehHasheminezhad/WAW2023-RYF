# This script contains functions that retrieve all the networks used in our
# research. There are seperate functions for retrieving networks from each of
# the 4 different sources: KONCET, Netzschleuder, ICON, and SNAP. collect_all()
# collects all the graphs in a list "graphs", without doing any preprocessing.


# Imports
import os
import shutil
import graph_tool.all as gt
import pandas as pd
import time
import urllib.request
import tarfile
import zipfile
import rarfile
import scipy.io
from scipy.sparse import find
import gzip
import io
import requests
import logging

# Read spreadsheet containing all networks to be collected:

# The destination "path" will also be used to create temp directories for
# downloading and unzipping files in this script. Furthermore, when checking
# node and edge numbers of collected networks and comparing them to networks
# listed in the network spreadsheet, a log describing irregularities will be put
# in a folder "log" here as well.

path = os.getcwd()
networks_path = os.path.join(path, "networks_spreadsheet.csv")
df = pd.read_csv(networks_path, delimiter=";")
#print(df)



# translate_names(from_, to_, df, isDirected) is given a dataframe and
# translates non index names of vertices to indices and returns a graph-tool
# format graph. Written by Rouzbeh Hasheminezhad
def translate_names(from_, to_, df):
    # List for all edges
    edges = []
    
    # Filling edges
    for ind, row in df.iterrows():
        edges.append((row[from_], row[to_]))

    # Dictionary for translation
    dic_ = {}
    new_edges = []
    index = 0
    # Filling dictionary
    for (a, b) in edges:
        if not a in dic_:
            dic_[a] = index
            index += 1
        if not b in dic_:
            dic_[b] = index
            index += 1

    # Creating new list of edges with index names
    for (a, b) in edges:
        new_edges.append((dic_[a], dic_[b]))
    
    # Creating gt graph
    g = gt.Graph(directed=False)
        
    # Finding number of vertices:
    nodes = 0
    for (a, b) in new_edges:
        if a > nodes:
            nodes = a
        if b > nodes:
            nodes = b
        
    # Adding vertices
    g.add_vertex((nodes+1))

    # Adding edges:
    g.add_edge_list(new_edges)
        
    return g

# add_properties(g, source, name) takes a graph-tool format graph "g" and adds 
# a source and possibly also a name property.
def add_properties(g, graphSource, graphName = ""):
    # Adding graph property for the source of the graph
    source = g.new_graph_property("string")                
    source[g] = graphSource
    g.graph_properties["source"] = source
    
    # Adding graph property for the name of the graph
    if graphName != "":
        name = g.new_graph_property("string")                 
        name[g] = graphName
        g.graph_properties["name"] = name

# collect_konect(internal_name) collects a graph from KONECT given the graphs
# KONECT internal name. It then calls parse_konect_network(file_path) to format
# the graph to graph-tool format before returning the formatted graph.

def collect_konect(internal_name):
    url = "http://konect.cc/files/download.tsv." + internal_name + ".tar.bz2"
    
    # Create a temporary directory to extract the tar and read the network from
    td = os.path.join(path, "temp_tar")
    os.mkdir(td)
    try:
        # Download the file from the URL
        tf = os.path.join(td, 'temp.tar.bz2')
        urllib.request.urlretrieve(url, tf)

        # Untar the file
        tar = tarfile.open(tf, "r:bz2") 
        tar.extractall(td)
        tar.close()
        
        # Remove tar again
        os.remove(tf)

        g = None
        for i in os.listdir(td):
            if i == ".DS_Store":
                    continue
            netdir = td + "/" + i
            for net in os.listdir(netdir):
                if net[:4] != "out.":
                    continue
                    
                # Parse network
                g = parse_konect_network(os.path.join(netdir, net))
                break
                
    except Exception as exc:
        print("============ KONECT collection failed with url: " + url + " ============")
        print(exc)
        
    finally:
        # Remove temp_tar directory again
        shutil.rmtree(td)
    return g

# parse_konect_network(file_path) takes the file path to a edgelist of a network
# from KONECT. It then reads this edgelist and converts it to graph-tool format
# and returns it.
def parse_konect_network(file_path):
    # Count amount of lines starting with "%" and skip that many rows
    file = open(file_path)
    skip = 0
    delimiter = " "
    for line in file.read().splitlines()[:10]:
        if line[0] == "%":
            skip = skip + 1
        elif "\t" in line:
            delimiter = "\t"
            
    
    Bf1 = pd.read_csv(file_path,
                  delimiter = delimiter, header = None, skiprows = skip, usecols = [0, 1])
    Bf1.columns = ["one", "two"]
    
    # Creating graph-tool format graph:
    return translate_names("one", "two", Bf1)

# find_skip(file_path) takes the path to an edgelist containing first a section
# describing the vertices of the network and next a section describing the edges
# of the network where the transition between the two sections is  marked with
# "*Edges". It then splits the the file at "*Edges" reads the edgelist section
# of the original file into a data frame which is then returned. In some cases
# there are also a final section describing triangles in the graphs marked with
# "*Triangles". The length of this section is also found and returned.
def find_skip(file_path): 
    file = open(file_path)
    skip = 0
    footer = 0
    edges = True
    triangles = False
    # Count lines to skip
    for line in file.read().splitlines():
        if edges: skip = skip + 1
        if line[:len("*Edges")] == "*Edges":
            edges = False
        if line[:len("*Triangles")] == "*Triangles":
            triangles = True
        if triangles: footer = footer + 1
            
    return [skip, footer]

# collect_snap() collects a network from SNAP. For every graph used in our
# research from SNAP the function returns the graph-tool format version of the
# original graph as stored on SNAP.
def collect_snap():
    # Create a temporary directory to extract the tar and read the network from
    td = os.path.join(path, "temp_tar")
    os.mkdir(td)
    
    # Download the three network collections from SNAP
    urls = ["https://snap.stanford.edu/data/git_web_ml.zip",              # musae-github 
           "https://snap.stanford.edu/data/twitch.zip",                   # musae-twitch
           "https://snap.stanford.edu/data/gemsec_deezer_dataset.tar.gz", # gemsec-Deezer
           ]
    try:
        for i in range(len(urls)):
            file_type = ".zip" if i < 2 else ".tar.gz"
            tf = os.path.join(td, str(i) + file_type)
            urllib.request.urlretrieve(urls[i], tf)
            
            # Unzip the file
            if i < 2:
                with zipfile.ZipFile(tf,"r") as zip_ref:
                    zip_ref.extractall(td)
            else:
                tar = tarfile.open(tf) 
                tar.extractall(td)
                tar.close()
            # Remove tar again
            os.remove(tf)
        
        graphs = {}
        
        # Read the networks:
        # gemsec-Deezer:
        for i in ["HR", "HU", "RO"]:
            Bf1 = pd.read_csv(td + "/deezer_clean_data/" + i + "_edges.csv",
                      delimiter = ",", header = None, skiprows = 1, usecols = [0, 1])
            Bf1.columns = ["one", "two"]
            
            # Creating graph-tool format graph:
            g = translate_names("one", "two", Bf1)
            name = "gemsec-Deezer/" + i
            add_properties(g, "SNAP", name)
            graphs[name] = g
            
        # musae-twitch:
        for i in ["DE/musae_DE", "ENGB/musae_ENGB", "ES/musae_ES", 
                  "FR/musae_FR", "PTBR/musae_PTBR", "RU/musae_RU"]:
            Bf1 = pd.read_csv(td + "/twitch/" + i + "_edges.csv",
                      delimiter = ",", header = None, skiprows = 1, usecols = [0, 1])
            Bf1.columns = ["one", "two"]
        
            # Creating graph-tool format graph:
            g = translate_names("one", "two", Bf1)
            name = "musae-twitch/" + i.split("/")[0]
            add_properties(g, "SNAP", name)
            graphs[name] = g
        
        # musae-github:
        Bf1 = pd.read_csv(td + "/git_web_ml/musae_git_edges.csv", #
                          delimiter = ",", header = None, skiprows = 1, usecols = [0, 1])
        Bf1.columns = ["one", "two"]
    
        # Creating graph-tool format graph:
        g = translate_names("one", "two", Bf1)
        name = "musae-github"
        add_properties(g, "SNAP", name)
        graphs[name] = g
        
    except Exception as exc:
        print("======== SNAP collection failed ========")
        print(exc)
        
    finally:            
        # Remove temp_tar directory again
        shutil.rmtree(td)
    return graphs

# collect_netzschleuder(name) is a function to collect a network from
# Netzschleuder. The function takes the Netzschleuder internal name of a network
# as an argument and returns the graph-tool formatted original graph as stored
# on Netzschleuder.
def collect_netzschleuder(name):
    # Collecting the network using graph-tool:
    try:
        g = gt.collection.ns[name]
        # Adding a "source" protperty to the graph clarifying its origin.
        add_properties(g, "Netzschleuder", name)
        
    except Exception as exc:
        print("======== Netzschleuder collection failed with name: " + name + " ========")
        print(exc)
        
    return g

# facebook100(names) takes a list of names of networks from the Facebook100
# collection and collects them. It then reads the graphs, converts them to the
# graph-tool format  and returns a list of all the collected graphs.
def new_facebook100(names):
    graphs = {}
    try: 
        td = os.path.join(path, "temp_100")
        os.mkdir(td)
    
        tf = os.path.join(td, "facebook100.zip")
        url = "https://archive.org/download/oxford-2005-facebook-matrix/facebook100.zip"
        urllib.request.urlretrieve(url, tf)
        
        # Unzip the file
        with zipfile.ZipFile(tf,"r") as zip_ref:
            zip_ref.extractall(td)

        # Remove zip again
        os.remove(tf)
            
        for i in names:
            if i == "Wash U32":
                i = "WashU32"
            # Reading the .mat format
            A = scipy.io.loadmat(
                os.path.join(td, "facebook100/" + i + ".mat")
                )["A"].tocsr().astype(bool)
            n = A.shape[0]
            sources, targets, _ = find(A)
            edges = []
            assert len(sources) == len(targets)
            for j in range(len(sources)):
                edges.append((sources[j], targets[j]))
            g = gt.Graph(directed=False)
            g.add_vertex(n)
            g.add_edge_list(edges)
        
            if i == "WashU32":
                i = "Wash U32"
            name = "Facebook100/" + i
            add_properties(g, "ICON", name)
            graphs[name] = g
    except Exception as exc:
        print("======== Facebook100 collection failed ========")
        print(exc)
        
    finally:
        # Remove temp_tar directory again
        shutil.rmtree(td)
        
    return graphs

# extract_rar(input_file, output_dir) extracts the .rar file located in
# "input_file" and places the extracted file in "output_dir".
def extract_rar(input_file, output_dir):
    with rarfile.RarFile(input_file, 'r') as archive:
        archive.extractall(path=output_dir)
    return

# collect_icon(facebook100_names) is a function to collect a network from ICON.
# The function takes a list of names of Facebook100 networks to collect as an
# argument and returns the graph-tool format version of all the original graphs
# used as they are stored on ICON.
def collect_icon(facebook100_names):
    graphs = new_facebook100(facebook100_names)
    
    td = os.path.join(path, "temp_icon")
    os.mkdir(td)
    
    # Download the three network collections from SNAP
    urls = [
        # AMiner scientific collaborations (2009)
            "https://www.aminer.org/lab-datasets/soinf/graphs_authors.rar", 
        # PGP web of trust (2004)
            "http://deim.urv.cat/~alexandre.arenas/data/xarxes/PGP.zip", 
        # WHOIS AS Internet (2006)
            "https://www.caida.org/catalog/papers/2005_tr_2005_02/supplemental/data_sources/WHOIS.gz", 
        # Flickr (2012)
            "http://snap.stanford.edu/data/flickrEdges.txt.gz",
        # Yeast interactome (2003)
            "http://vlado.fmf.uni-lj.si/pub/networks/data/bio/Yeast/yeast.zip", 
        # Myocardial inflammation proteins (2011)
            "https://static-content.springer.com/esm/art%3A10.1186%2F1755-8794-4-59/MediaObjects/12920_2011_252_MOESM1_ESM.XLS", 
        # Binary interactomes (various species; 2012)/A. thaliana (mustard)
            "http://hint.yulab.org/old_versions/Before_2019/ArabidopsisThaliana_binary_hq.txt", 
        # Binary interactomes (various species; 2012)/C. elegans (nematode)
            "http://hint.yulab.org/old_versions/Before_2019/CaenorhabditisElegans_binary_hq.txt",
        # Binary interactomes (various species; 2012)/D. melanogaster (fly)
            "http://hint.yulab.org/old_versions/Before_2019/DrosophilaMelanogaster_binary_hq.txt", 
        # Binary interactomes (various species; 2012)/E. coli K12
            "http://hint.yulab.org/old_versions/Before_2019/EscherichiaColiK12_binary_hq.txt",
        # Binary interactomes (various species; 2012)/H. sapiens (human)
            "http://hint.yulab.org/old_versions/Before_2019/HomoSapiens_binary_hq.txt",
        # Binary interactomes (various species; 2012)/M. musculus (mouse)
            "http://hint.yulab.org/old_versions/Before_2019/MusMusculus_binary_hq.txt",
        # Binary interactomes (various species; 2012)/S. cerevisiae S288C (budding yeast)
            "http://hint.yulab.org/old_versions/Before_2019/SaccharomycesCerevisiaeS288C_binary_hq.txt",
        # Reguly yeast interactome (2006)
            "http://interactome.dfci.harvard.edu/S_cerevisiae/download/LC_multiple.txt",
        # S. cerevisiae interactome (2008)
            "http://math.bu.edu/people/kolaczyk/datasets/ppi.zip",
        # India bus routes (2016)/ - all subnetworks
            "https://github.com/achatterjee3/Dataset/raw/master/Bus%20data.rar",
        # UK public transportation (2004-2011)/edges_rail
            "https://bitbucket.org/deregtr/gb_ptn/raw/3475dfefd4a85ec4bd4cb92df34153e84b52eaa4/edges_rail.dat",
           ]
    
    # Now we iterate over the URLs and handle each format one at a time
    for i in range(len(urls)):

        try:

            if urls[i][-4:] == ".rar":   
                tf = os.path.join(td, str(i) + ".rar")
                urllib.request.urlretrieve(urls[i], tf)
                
                # Unrar the file
                extract_rar(tf, td)
                
                # AMiner scientific collaborations (2009)/AMiner DatabaseSys sub0 coauthors
                if urls[i][-18:] == "graphs_authors.rar":
                    fp = os.path.join(td, "graph-T24_sub0.net")
                    skip, footer = find_skip(fp)
                    Bf1 = pd.read_csv(fp, delimiter = " ", header = None, usecols = [0, 1],
                                      skiprows = skip, skipfooter = footer)
                    Bf1.columns = ["one", "two"]
                    g = translate_names("one", "two", Bf1)
                    name = "AMiner scientific collaborations (2009)/AMiner DatabaseSys sub0 coauthors"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                
                # India bus routes (2016)/ - all subnetworks
                if urls[i][-14:] == "Bus%20data.rar":
                    files = ["HBN_Hyderabad", "ABN_Ahmedabad", "CBN_Chennai", "DBN_Delhi"]
                    for j in files:
                        fp = os.path.join(td, "Bus data", j[:3].lower() + ".txt")
                        Bf1 = pd.read_csv(
                            fp, delimiter = "\t", header = None, usecols = [0, 1], skiprows = 1)
                        Bf1.columns = ["one", "two"]
                        g = translate_names("one", "two", Bf1)
                        name = "India bus routes (2016)/India_bus_"+j+"_2016"
                        add_properties(g, "ICON", name)
                        graphs[name] = g
                
                # Remove tar again
                os.remove(tf)
                
            if urls[i][-4:] == ".zip":
                tf = os.path.join(td, str(i) + ".zip")
                if urls[i][-7:] == "PGP.zip":
                    r = requests.get(urls[i], verify = False)
                    open(tf, "wb").write(r.content)
                else:
                    urllib.request.urlretrieve(urls[i], tf)
                
                # Unzip the file
                with zipfile.ZipFile(tf,"r") as zip_ref:
                    zip_ref.extractall(td)
                
                # Remove tar again
                os.remove(tf)
                
                # PGP web of trust (2004)
                if urls[i][-7:] == "PGP.zip": 
                    fp = os.path.join(td, "PGPgiantcompo.net")
                    Bf1 = pd.read_csv(
                        fp, delimiter = " ", header = None, usecols = [0, 1],
                        skiprows = find_skip(fp)[0])
                    Bf1.columns = ["one", "two"]
                                    
                    # Creating graph-tool format graph:
                    g = translate_names("one", "two", Bf1)
                    name = "PGP web of trust (2004)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                
                # Yeast interactome (2003)
                if urls[i][-9:] == "yeast.zip":
                    # Reading file
                    file = open(os.path.join(td, "Yeast.paj"))
                    skip = True
                    
                    # Read edligelist into a list object
                    edges = []
                    for line in file.read().splitlines():
                        if line[:6] == "*Edges" and skip:
                            skip = False
                            continue
                        elif skip:
                            continue
                        elif line[:6] == "*Edges":
                            break
                    
                        elements = line[1:].split(" ")
                        edges.append([int(elements[0]), int(elements[1])])

                    Bf1 = df = pd.DataFrame(edges, columns = ['one', 'two'])
                    
                    # Creating graph-tool format graph:
                    g = translate_names("one", "two", Bf1)
                    name = "Yeast interactome (2003)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                    
                # ---S. cerevisiae interactome (2008)
                if urls[i][-7:] == "ppi.zip": 
                    Bf1 = pd.read_csv(os.path.join(td, "ppi.txt"),
                              delimiter = "\t", header = None, usecols = [0, 1])
                    Bf1.columns = ["one", "two"]
                
                    # Creating graph-tool format graph:
                    g = translate_names("one", "two", Bf1)
                    name = "S. cerevisiae interactome (2008)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                
            if urls[i][-3:] == ".gz":
                # Download file
                tf = os.path.join(td, str(i) + ".txt.gz")
                urllib.request.urlretrieve(urls[i], tf)
                
                # Unpack file
                f=gzip.open(tf,'rt')
                file_content=f.read()
                
                # WHOIS AS Internet (2006):                 
                if urls[i][-8:] == "WHOIS.gz":
                    Bf1 = pd.read_csv(io.StringIO(file_content),
                              delimiter = " ", header = None, usecols = [0, 1])
                    Bf1.columns = ["one", "two"]
                    
                    # Creating graph-tool format graph:
                    g = translate_names("one", "two", Bf1)
                    name = "WHOIS AS Internet (2006)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                    
                # Flickr (2012):                 
                if urls[i][-18:] == "flickrEdges.txt.gz":
                    Bf1 = pd.read_csv(io.StringIO(file_content),
                              delimiter = " ", header = None, usecols = [0, 1], skiprows = 4)
                    Bf1.columns = ["one", "two"]
                    
                    # Creating graph-tool format graph:
                    g = translate_names("one", "two", Bf1)
                    name = "Flickr (2012)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g   
                
                # Remove gz again
                os.remove(tf)
                    
            if urls[i][-4:] == ".txt" or urls[i][-4:] == ".dat":
                file = urllib.request.urlopen(urls[i])
                string = file.read().decode('utf-8')
                
                # Binary interactomes (various species; 2012):
                if urls[i][-13:] == "binary_hq.txt":
                    full_name = urls[i].split("/")[-1][:-14]
                    name = "A. thaliana (mustard)"
                    if full_name == "CaenorhabditisElegans":
                        name = "C. elegans (nematode)"
                    elif full_name == "DrosophilaMelanogaster":
                        name = "D. melanogaster (fly)"
                    elif full_name == "EscherichiaColiK12":
                        name = "E. coli K12"
                    elif full_name == "HomoSapiens":
                        name = "H. sapiens (human)"
                    elif full_name == "MusMusculus":
                        name = "M. musculus (mouse)"
                    elif full_name == "SaccharomycesCerevisiaeS288C":
                        name = "S. cerevisiae S288C (budding yeast)"

                    Bf1 = pd.read_csv(io.StringIO(string), sep = "\t")
                    g = translate_names("Uniprot_A", "Uniprot_B", Bf1)
                    full_name = "Binary interactomes (various species; 2012)/" + name
                    add_properties(g, "ICON", full_name)
                    graphs[full_name] = g  
                    
                # Reguly yeast interactome (2006):
                if urls[i][-15:] == "LC_multiple.txt":
                    Bf1 = pd.read_csv(io.StringIO(string), sep = "\t", header = None)
                    Bf1.columns = ["one", "two"]
                    g = translate_names("one", "two", Bf1)
                    name = "Reguly yeast interactome (2006)"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                    
                # UK public transportation (2004-2011)/edges_rail:
                if urls[i][-14:] == "edges_rail.dat":
                    Bf1 = pd.read_csv(io.StringIO(string), delim_whitespace = True, header = None)
                    Bf1.columns = ["one", "two"]
                    g = translate_names("one", "two", Bf1)
                    name = "UK public transportation (2004-2011)/edges_rail"
                    add_properties(g, "ICON", name)
                    graphs[name] = g
                    
            if urls[i][-4:] == ".XLS":
                # Myocardial inflammation proteins (2011)
                tf = os.path.join(td, "Myocardial.xls")
                file = urllib.request.urlretrieve(urls[i], tf)
                data = pd.read_excel(tf, sheet_name = "My-Inflamome", header = None)
                Bf1 = pd.DataFrame(data)
                Bf1.columns = ["one", "type", "two"]
                g = translate_names("one", "two", Bf1)
                name = "Myocardial inflammation proteins (2011)"
                add_properties(g, "ICON", name)
                graphs[name] = g
    
        except Exception as exc:
            print("======== Failed collecting ICON network: " + urls[i] + " ========")
            print(exc)
            
    # Remove temp directory again
    shutil.rmtree(td)
    return graphs

# collect_all() collects all networks from the dataframe "df". It stores the
# result in the python list "graphs" which contains the graphs in graph-tool
# format (.gt).
def collect_all():
    start_NnK = time.time()
    graphs = {}
    facebook100 = []
    
    for index, row in df.iterrows():
        print(row["Name"])
        if row["Source"] == "Netzschleuder":
            graphs[row["Name"]] = collect_netzschleuder(row["Name"])
            
        if row["Source"] == "KONECT":
            # in the name of a KONECT network, the KONECT internal name is stored
            # in square brackets after the external name. Below we extract the internal name.
            graphs[row["Name"]] = collect_konect(row["Name"].split("[")[-1].split("]")[0])
            print(graphs[row["Name"]])
            
        if row["Source"] == "ICON":
            if row["Name"][:11] == "Facebook100":
                facebook100.append(row["Name"].split("/")[1])
                
        if row["Source"] == "SNAP":
            # Do nothing - handle below
            continue
    
    print("Finished collecting Netzschleuder and KONECT graphs")
    end_NnK = time.time()
    print("--- Netzschleuder and Konect: " + str(end_NnK - start_NnK))
    
    # Collect networks from SNAP and ICON seperately
    start_S = time.time()
    graphs = {**graphs, **collect_snap()}
    end_S = time.time()
    print("--- Snap: " + str(end_S - start_S))

    start_I = time.time()
    graphs = {**graphs, **collect_icon(facebook100)}
    print("Finished collecting ICON graphs")
    end_I = time.time()
    print("--- Icon: " + str(end_I - start_I))

    return graphs

# pre_process(g) takes a graph-tool formatted graph "g" as an argument and
# returns the graph in a pre-processed state. This includes removing self-loops,
# parallel edges, and anything  not in the largest connected component.
def pre_process(g):
    gt.remove_self_loops(g)
    gt.remove_parallel_edges(g)
    g = gt.extract_largest_component(g, prune=True)
    return g

# ------------------------------------------------ #
# --------------- Running the code --------------- #
# ------------------------------------------------ #
# Collecting networks
start = time.time()
raw = collect_all()
end = time.time()
print("--- Total: " + str(end - start))

# Pre-processing
pre_processed = {}
for i in raw:
    pre_processed[i] = pre_process(raw[i])
print("Finished pre-processing: "+str(len(pre_processed))+" networks")

# ------------------------------------------------ #
# ------------- Storing the networks ------------- #
# ------------------------------------------------ #
path = os.getcwd()
networks = os.path.join(path, "networks")
os.mkdir(networks)
categories = ["Technological", "Social", "Biological", "Transportation", "Auxiliary"]
for i in categories:
    os.mkdir(os.path.join(networks, i))
    


for i in pre_processed:
    # Find category of network i
    category = df.loc[df['Name'] == i]["Category"].iloc[0]
    category_path = os.path.join(networks, category)
    
    # Make sub_network unique directory:
    net = i
    subnet = i
    if i.__contains__("/"):
        net = i.split("/")[0]
        subnet = net + " (" + i.split("/")[1] + ")"
    elif i.__contains__("["):
        net = i.split("[")[0][:-1]
        subnet = net
    collection_path = os.path.join(category_path, net)
    if not os.path.isdir(collection_path):
        os.mkdir(collection_path)
    subnet_path = os.path.join(collection_path, subnet)
    os.mkdir(subnet_path)

    # Populate sub_network unique directory:
    graph_path = os.path.join(subnet_path, "Graph-Data")
    os.mkdir(graph_path)
    os.mkdir(os.path.join(subnet_path, "Robustness-Score-Data"))
    os.mkdir(os.path.join(subnet_path, "Scalefreeness-Score-Data"))

    pre_processed[i].save(os.path.join(graph_path, subnet + ".gt"))
