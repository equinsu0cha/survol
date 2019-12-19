import os
import sys
import psutil
import rdflib
import rdflib.plugins.memory

################################################################################

survol_url = "http://primhillcomputer.com/ontologies/"
class_CIM_Process = rdflib.term.URIRef(survol_url + "CIM_Process")
class_CIM_Directory = rdflib.term.URIRef(survol_url + "CIM_Directory")
class_CIM_DataFile = rdflib.term.URIRef(survol_url + "CIM_DataFile")

predicate_Handle = rdflib.term.URIRef(survol_url + "Handle")
predicate_Name = rdflib.term.URIRef(survol_url + "Name")

# This is not part of the ontology but allows to return several processes,
# based on their parent process id.
predicate_ParentProcessId = rdflib.term.URIRef(survol_url + "ParentProcessId")

associator_CIM_DirectoryContainsFile = rdflib.term.URIRef(survol_url + "CIM_DirectoryContainsFile")
associator_CIM_ProcessExecutable = rdflib.term.URIRef(survol_url + "CIM_ProcessExecutable")
################################################################################
def add_ontology(graph):
    graph.add((class_CIM_Process, rdflib.namespace.RDF.type, rdflib.namespace.RDFS.Class))
    graph.add((class_CIM_Process, rdflib.namespace.RDFS.label, rdflib.Literal("CIM_Process")))
    graph.add((class_CIM_Directory, rdflib.namespace.RDF.type, rdflib.namespace.RDFS.Class))
    graph.add((class_CIM_Directory, rdflib.namespace.RDFS.label, rdflib.Literal("CIM_Directory")))
    graph.add((class_CIM_DataFile, rdflib.namespace.RDF.type, rdflib.namespace.RDFS.Class))
    graph.add((class_CIM_DataFile, rdflib.namespace.RDFS.label, rdflib.Literal("CIM_DataFile")))

    graph.add((predicate_Handle, rdflib.namespace.RDF.type, rdflib.namespace.RDF.Property))
    graph.add((predicate_Handle, rdflib.namespace.RDFS.domain, class_CIM_Process))
    graph.add((predicate_Handle, rdflib.namespace.RDFS.range, rdflib.namespace.XSD.integer))
    graph.add((predicate_Handle, rdflib.namespace.RDFS.label, rdflib.Literal("Handle")))
    graph.add((predicate_Handle, rdflib.namespace.RDFS.range, rdflib.namespace.XSD.integer))

    graph.add((predicate_ParentProcessId, rdflib.namespace.RDF.type, rdflib.namespace.RDF.Property))
    graph.add((predicate_ParentProcessId, rdflib.namespace.RDFS.domain, class_CIM_Process))
    graph.add((predicate_ParentProcessId, rdflib.namespace.RDFS.range, rdflib.namespace.XSD.string))
    graph.add((predicate_ParentProcessId, rdflib.namespace.RDFS.label, rdflib.Literal("ParentProcessId")))

    graph.add((predicate_Name, rdflib.namespace.RDF.type, rdflib.namespace.RDF.Property))
    graph.add((predicate_Name, rdflib.namespace.RDFS.domain, class_CIM_Directory))
    graph.add((predicate_Name, rdflib.namespace.RDFS.domain, class_CIM_DataFile))
    graph.add((predicate_Name, rdflib.namespace.RDFS.range, rdflib.namespace.XSD.string))
    graph.add((predicate_Name, rdflib.namespace.RDFS.label, rdflib.Literal("Name")))

    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDF.type, rdflib.namespace.RDF.Property))
    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDFS.domain, class_CIM_Directory))
    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDFS.range, class_CIM_DataFile))
    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDFS.range, class_CIM_Directory))
    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDFS.range, rdflib.namespace.XSD.string))
    graph.add((associator_CIM_DirectoryContainsFile, rdflib.namespace.RDFS.label, rdflib.Literal("CIM_DirectoryContainsFile")))

    graph.add((associator_CIM_ProcessExecutable, rdflib.namespace.RDF.type, rdflib.namespace.RDF.Property))
    graph.add((associator_CIM_ProcessExecutable, rdflib.namespace.RDFS.domain, class_CIM_Process))
    graph.add((associator_CIM_ProcessExecutable, rdflib.namespace.RDFS.range, class_CIM_DataFile))
    graph.add((associator_CIM_ProcessExecutable, rdflib.namespace.RDFS.label, rdflib.Literal("CIM_ProcessExecutable")))

################################################################################

is_platform_windows = sys.platform.startswith("win")
is_platform_linux = sys.platform.startswith("linux")

def equal_paths(path_a, path_b):
    # print("process_executable=", process_executable, "executable_path=", executable_path)
    # With pytest as a command line: "c:\python27\python.exe" != "C:\Python27\python.exe"
    if is_platform_linux:
        return path_a == path_b
    elif is_platform_windows:
        return path_a.upper() == path_b.upper()
    else:
        raise Exception("Invalid platform")

def is_usable_file(file_path):
    if os.path.isfile(file_path):
        return True
    if is_platform_linux:
        if os.path.islink(file_path):
            return True
    return False

################################################################################

def current_function():
    return sys._getframe(1).f_code.co_name

class Sparql_CIM_Object(object):
    def __init__(self, class_name, key_variable):
        self.m_variable = key_variable
        self.m_class_name = class_name
        self.m_associators = {}
        self.m_associated = {}
        self.m_properties = {}

    def __str__(self):
        def kw_to_str(property, value):
            property_str = str(property)[len(survol_url):]
            value_str = str(value)
            return "%s=%s" % (property_str, value_str)

        # print("ka=", self.m_known_attributes.items())
        kw = ".".join([ kw_to_str(property, value) for property, value in self.m_properties.items()])
        return "Sparql_CIM_Object:" + self.m_class_name + ":" + self.m_variable + ":" + kw

    def FetchAllVariables(self, graph, variables_context):
        print("FetchAllVariables not implemented")
        raise NotImplementedError(current_function())

    def CalculateVariablesNumber(self):
        self.m_number_variables = 0
        self.m_number_literals = 0
        # FIXME: No need to list the associators which contains only instances. Logic should be different.
        for one_dict in [self.m_associators, self.m_associated, self.m_properties]:
            for key, value in one_dict.items():
                if isinstance(value, rdflib.term.Variable):
                    self.m_number_variables += 1
                elif isinstance(value, rdflib.term.Literal):
                    self.m_number_literals += 1

    def GetNodeValue(self, predicate_node, variables_context):
        predicate_variable = self.m_properties[predicate_node]
        if isinstance(predicate_variable, rdflib.term.Literal):
            node_value = predicate_variable
        elif isinstance(predicate_variable, rdflib.term.Variable):
            if predicate_variable not in variables_context:
                print("GetNodeValue QUIT:", predicate_variable, "not in", variables_context.keys())
                return None
            node_value = variables_context[predicate_variable]
            print("predicate_variable=", predicate_variable, "node_value=", node_value)
            assert isinstance(node_value, rdflib.term.Literal)
        return node_value


class Sparql_CIM_DataFile(Sparql_CIM_Object):
    def __init__(self, class_name, node):
        super(Sparql_CIM_DataFile, self).__init__(class_name, node)

    def FetchFromProperties(self, variables_context):
        print("Sparql_CIM_DataFile.FetchFromProperties")
        if predicate_Name in self.m_properties:
            return self.GetNodeValue(predicate_Name, variables_context)
        else:
            print("Sparql_CIM_DataFile QUIT: No Name")
            return None


    def FetchFromDirectory(self, variables_context, file_path, graph, returned_variables, node_uri_ref):
        print("Sparql_CIM_DataFile.FetchFromDirectory file_path=", file_path)
        if associator_CIM_DirectoryContainsFile in self.m_associated:
            associator_instance = self.m_associated[associator_CIM_DirectoryContainsFile]
            assert isinstance(associator_instance, Sparql_CIM_Directory)
            assert isinstance(associator_instance.m_variable, rdflib.term.Variable)

            if associator_instance.m_variable in variables_context:
                print("ALREADY DEFINED ??", associator_instance.m_variable)
                return

            dir_file_path = os.path.dirname(file_path)
            dir_file_path_node = rdflib.term.Literal(dir_file_path)

            dir_node_str = "Machine:CIM_Directory?Name=" + dir_file_path
            associator_instance_url = rdflib.term.URIRef(dir_node_str)
            graph.add((associator_instance_url, rdflib.namespace.RDF.type, class_CIM_Directory))
            graph.add((associator_instance_url, associator_CIM_DirectoryContainsFile, node_uri_ref))

            if predicate_Name in associator_instance.m_properties:
                dir_path_variable = associator_instance.m_properties[predicate_Name]
                assert isinstance(dir_path_variable, rdflib.term.Variable)
            else:
                # This property must be created, to make the directory usable,
                # for example to get its other properties.
                # Generally speaking, this must be done for all properties of the ontology.
                variable_name = str(associator_instance.m_variable) + "_dummy_name"
                dir_path_variable = rdflib.term.Variable(variable_name)
                associator_instance.m_properties[predicate_Name] = dir_path_variable

            if isinstance(dir_path_variable, rdflib.term.Variable):
                returned_variables[(associator_instance.m_variable, dir_path_variable)] = [(associator_instance_url, dir_file_path_node)]
            else:
                returned_variables[associator_instance.m_variable] = [associator_instance_url]
            graph.add((associator_instance_url, predicate_Name, dir_file_path_node))

    def FetchAllVariables(self, graph, variables_context):
        node_file_path = self.FetchFromProperties(variables_context)
        if not node_file_path:
            return {}
        file_path = str(node_file_path)
        returned_variables = {}

        url_as_str = "Machine:CIM_DataFile?Name=" + file_path
        node_uri_ref = rdflib.term.URIRef(url_as_str)
        graph.add((node_uri_ref, rdflib.namespace.RDF.type, class_CIM_DataFile))

        returned_variables[self.m_variable] = [node_uri_ref]

        # No need to add node_file_path in the results because,
        # if it is a Variable, it is already in the context.
        assert isinstance(self.m_variable, rdflib.term.Variable)
        assert node_file_path
        graph.add((node_uri_ref, predicate_Name, node_file_path))

        assert associator_CIM_DirectoryContainsFile not in self.m_associators

        self.FetchFromDirectory(variables_context, file_path, graph, returned_variables, node_uri_ref)

        # TODO: If there are no properties and no directory, this should return ALL FILES OF THE FILE SYSTEM.

        return returned_variables

class Sparql_CIM_Directory(Sparql_CIM_DataFile):
    def __init__(self, class_name, node):
        super(Sparql_CIM_Directory, self).__init__(class_name, node)

    def FetchAllVariables(self, graph, variables_context):
        node_file_path = self.FetchFromProperties(variables_context)
        if not node_file_path:
            print("Sparql_CIM_Directory.FetchAllVariables LEAVING DOING NOTHING !!!!!")
            return {}
        file_path = str(node_file_path)
        returned_variables = {}

        url_as_str = "Machine:CIM_Directory?Name=" + file_path
        node_uri_ref = rdflib.term.URIRef(url_as_str)

        assert isinstance(self.m_variable, rdflib.term.Variable)
        returned_variables[self.m_variable] = [node_uri_ref]
        graph.add((node_uri_ref, rdflib.namespace.RDF.type, class_CIM_Directory))

        # No need to add node_file_path in the results=:
        # This Variable is already in the context.
        assert node_file_path
        graph.add((node_uri_ref, predicate_Name, node_file_path))

        self.FetchFromDirectory(variables_context, file_path, graph, returned_variables, node_uri_ref)

        if associator_CIM_DirectoryContainsFile in self.m_associators:
            associated_instance = self.m_associators[associator_CIM_DirectoryContainsFile]
            assert isinstance(associated_instance, (Sparql_CIM_DataFile, Sparql_CIM_Directory))
            assert isinstance(associated_instance.m_variable, rdflib.term.Variable)

            return_values_list = []

            if predicate_Name in associated_instance.m_properties:
                dir_path_variable = associated_instance.m_properties[predicate_Name]
                print("dir_path_variable=", dir_path_variable, type(dir_path_variable))
                print("Sparql_CIM_Directory.FetchAllVariables dir_path_variable=", dir_path_variable)
            else:
                # This creates a temporary variable to store the name because
                # it might be necessary to identify this associated instance.
                # This is needed for all properties of the ontology.
                variable_name = str(associated_instance.m_variable) + "_dummy_subname"
                dir_path_variable = rdflib.term.Variable(variable_name)
                associated_instance.m_properties[predicate_Name] = dir_path_variable
                print("Sparql_CIM_Directory.FetchAllVariables Created dummy variable:", variable_name)

            def add_sub_node(sub_node_str, cim_class, sub_path_name):
                # print("Sparql_CIM_Directory.FetchAllVariables add_sub_node ", sub_node_str, "sub_path_name=", sub_path_name)
                # WARNING("Sparql_CIM_Directory.FetchAllVariables add_sub_node %s / path=%s" % (sub_node_str, sub_path_name))
                assert cim_class in (class_CIM_Directory, class_CIM_DataFile)
                sub_node_uri_ref = rdflib.term.URIRef(sub_node_str)
                graph.add((sub_node_uri_ref, rdflib.namespace.RDF.type, cim_class))
                #sub_uri_ref_list.append(sub_node_uri_ref)
                sub_path_name_url = rdflib.term.Literal(sub_path_name)
                graph.add((sub_node_uri_ref, predicate_Name, sub_path_name_url))
                graph.add((node_uri_ref, associator_CIM_DirectoryContainsFile, sub_node_uri_ref))

                if isinstance(dir_path_variable, rdflib.term.Variable):
                    return_values_list.append((sub_node_uri_ref, sub_path_name_url))
                else:
                    return_values_list.append(sub_node_uri_ref)
                    assert isinstance(dir_path_variable, rdflib.term.Literal)
                    #print("Associated object Name is literal:", dir_path_variable)

            print("Sparql_CIM_Directory.FetchAllVariables file_path=", file_path)
            for root_dir, dir_lists, files_list in os.walk(file_path):
                if associated_instance.m_class_name == "CIM_Directory":
                    for one_file_name in dir_lists:
                        sub_path_name = os.path.join(root_dir, one_file_name)
                        # This must be a directory, possibly unreadable due to access rights.
                        assert os.path.isdir(sub_path_name)
                        sub_node_str = "Machine:CIM_Directory?Name=" + sub_path_name
                        add_sub_node(sub_node_str, class_CIM_Directory, sub_path_name)
                elif associated_instance.m_class_name == "CIM_DataFile":
                    for one_file_name in files_list:
                        sub_path_name = os.path.join(root_dir, one_file_name)
                        print("sub_path_name=", sub_path_name)
                        # This must be a file, possibly unreadable due to access rights, or a symbolic link.
                        assert is_usable_file(sub_path_name)



                        sub_node_str = "Machine:CIM_DataFile?Name=" + sub_path_name
                        add_sub_node(sub_node_str, class_CIM_DataFile, sub_path_name)
                else:
                    raise Exception("Cannot happen")
                # Loop on first level only.
                break

            print("Sparql_CIM_Directory.FetchAllreturn_values_list", return_values_list)
            if isinstance(dir_path_variable, rdflib.term.Variable):
                print("Sparql_CIM_Directory.FetchAllVariables Returning variables pair:", associated_instance.m_variable, dir_path_variable)
                returned_variables[(associated_instance.m_variable, dir_path_variable)] = return_values_list
            else:
                print("Sparql_CIM_Directory.FetchAllVariables Returning variable:", associated_instance.m_variable)
                returned_variables[associated_instance.m_variable] = return_values_list

            print("Sparql_CIM_Directory.FetchAllVariables FetchAllVariables returned_variables=", returned_variables)

        # TODO: If there are no properties and no directory and no sub-files or sub-directories,
        # TODO: this should return ALL DIRECTORIES OF THE FILE SYSTEM.

        return returned_variables



class Sparql_CIM_Process(Sparql_CIM_Object):
    def __init__(self, class_name, node):
        super(Sparql_CIM_Process, self).__init__(class_name, node)

    # Several properties can be used to return one or several objects.
    # TODO: We could use several properties at one: It is difficult to generalise.
    class PropertyDefinition:
        class property_definition_Handle:
            s_property_node = predicate_Handle

            def IfLiteralOrDefinedVariable(self, node_value):
                process_id = int(str(node_value))
                parent_process_pid =  psutil.Process(process_id).ppid()
                parent_process_pid_node = rdflib.term.Literal(parent_process_pid)

                return (predicate_Handle, predicate_ParentProcessId), [(node_value, rdflib.term.Literal(parent_process_pid))]

        class property_definition_ParentProcessId:
            s_property_node = predicate_ParentProcessId

            def IfLiteralOrDefinedVariable(self, node_value):
                ppid = int(str(node_value))
                list_values = [
                    (rdflib.term.Literal(child_process.pid), node_value)
                    for child_process in psutil.Process(ppid).children(recursive=False)]
                return (predicate_Handle, predicate_ParentProcessId), list_values

        g_properties = [
            property_definition_Handle(),
            property_definition_ParentProcessId()
        ]

    # If no property is usable, this returns all objects.
    # This can work only for some classes, if there are not too many objects.
    def GetAllObjects(self):
        print("Sparql_CIM_Process.GetAllObjects: Getting all processes")
        result_list = []

        list_values = [
            (rdflib.term.Literal(proc.pid), rdflib.term.Literal(proc.ppid()))
            for proc in psutil.process_iter()]
        return (predicate_Handle, predicate_ParentProcessId), list_values

    # This returns key-value pairs defining objects.
	# It returns all properties defined in the instance,
	# not only the properties of the ontology.
    def GetListOfOntologyProperties(self, variables_context):
        print("GetListOfOntologyProperties")
        for one_property in self.PropertyDefinition.g_properties:
            print("    GetListOfOntologyProperties one_property=", one_property.s_property_node)
            if one_property.s_property_node in self.m_properties:
                node_value = self.GetNodeValue(one_property.s_property_node, variables_context)
                if node_value:
                    assert isinstance(node_value, rdflib.term.Literal)
                    url_nodes_list = one_property.IfLiteralOrDefinedVariable(node_value)
                    return url_nodes_list
        print("GetListOfOntologyProperties leaving: Cannot find anything.")
        return None, None

    def CreateURIRef(self, graph, class_name, class_node, dict_predicates_to_values):
        url_as_str = "Machine:" + class_name
        delimiter = "?"
        for node_predicate, node_value in dict_predicates_to_values.items():
            predicate_name = str(node_predicate)[len(survol_url):]
            str_value = str(node_value)
            url_as_str += delimiter + "%s=%s" % (predicate_name, str_value)
            delimiter = "."
        print("CreateURIRef url_as_str=", url_as_str)
        node_uri_ref = rdflib.term.URIRef(url_as_str)
        graph.add((node_uri_ref, rdflib.namespace.RDF.type, class_node))

        for node_predicate, node_value in dict_predicates_to_values.items():
            assert isinstance(node_value, rdflib.term.Literal)
            graph.add((node_uri_ref, node_predicate, node_value))
        return node_uri_ref

    # Given the process id, it creates the file representing the executable being run.
    def DefineExecutableFromProcess(self, variables_context, process_id, graph, returned_variables, node_uri_ref):
        print("Sparql_CIM_Process.DefineExecutableFromProcess process_id=", process_id)
        if associator_CIM_ProcessExecutable in self.m_associators:
            associated_instance = self.m_associators[associator_CIM_ProcessExecutable]
            assert isinstance(associated_instance, Sparql_CIM_DataFile)
            assert isinstance(associated_instance.m_variable, rdflib.term.Variable)
            assert isinstance(process_id, int)

            # This calculates the variable which defines the executable node.
            assert associated_instance.m_variable not in variables_context

            # TODO: This could also explore DLLs, not only the main executable.
            executable_path = psutil.Process(process_id).exe()
            executable_path_node = rdflib.term.Literal(executable_path)

            associated_instance_url = self.CreateURIRef(graph, "CIM_DataFile", class_CIM_DataFile,
                         {predicate_Name: executable_path_node})

            graph.add((node_uri_ref, associator_CIM_ProcessExecutable, associated_instance_url))

            if predicate_Name in associated_instance.m_properties:
                dir_path_variable = associated_instance.m_properties[predicate_Name]
                assert isinstance(dir_path_variable, rdflib.term.Variable)
            else:
                # This property must be created, to make the directory usable,
                # for example to get its other properties.
                # Generally speaking, this must be done for all properties of the ontology.
                variable_name = str(associated_instance.m_variable) + "_dummy_name"
                dir_path_variable = rdflib.term.Variable(variable_name)
                associated_instance.m_properties[predicate_Name] = dir_path_variable

            if isinstance(dir_path_variable, rdflib.term.Variable):
                assert (associated_instance, dir_path_variable) not in returned_variables
                returned_variables[(associated_instance.m_variable, dir_path_variable)] = [
                    (associated_instance_url, executable_path_node)]
            else:
                assert associated_instance.m_variable not in returned_variables
                returned_variables[associated_instance.m_variable] = [associated_instance_url]
            graph.add((associated_instance_url, predicate_Name, executable_path_node))

    # Given a file name, it returns all processes executing it.
    def GetProcessesFromExecutable(self, graph, variables_context):

        print("Sparql_CIM_Process.GetProcessesFromExecutable executable=", sys.executable)
        associated_instance = self.m_associators[associator_CIM_ProcessExecutable]
        assert isinstance(associated_instance, Sparql_CIM_DataFile)
        assert isinstance(associated_instance.m_variable, rdflib.term.Variable)
        assert associated_instance.m_variable in variables_context
        associated_executable_node = variables_context[associated_instance.m_variable]
        assert isinstance(associated_executable_node, rdflib.term.URIRef)

        print("Sparql_CIM_Process.GetProcessesFromExecutable variables_context=", variables_context)
        print("associated_instance.m_variable=", associated_instance.m_variable)
        executable_node = associated_instance.GetNodeValue(predicate_Name, variables_context)
        assert isinstance(executable_node, rdflib.term.Literal)
        executable_path = str(executable_node)

        # Because of backslashes transformed into slashes, which is necessary because of Sparql.
        executable_path = os.path.normpath(executable_path)
        if is_platform_linux:
            executable_path = os.path.realpath(executable_path)
            print("executable_path=", executable_path)

        process_urls_list = []
        for one_process in psutil.process_iter():
            try:
                process_executable = one_process.exe()
            except psutil.AccessDenied as exc:
                print("GetProcessesFromExecutable Caught:", exc)
                continue
            # print("process_executable=", process_executable, "executable_path=", executable_path)
            # With pytest as a command line: "c:\python27\python.exe" != "C:\Python27\python.exe"

            # On Linux, it might be a symbolic link: /usr/bin/python3 and /usr/bin/python3.6
            if equal_paths(executable_path, process_executable):
                process_url = self.CreateURIRef(
                    graph, "CIM_Process", class_CIM_Process,
                    {predicate_Handle: rdflib.term.Literal(one_process.pid)})
                print("Adding process ", process_url)
                graph.add((process_url, associator_CIM_ProcessExecutable, associated_executable_node))
                process_urls_list.append(process_url)
        return process_urls_list
        print("GetProcessesFromExecutable process_urls_list=", process_urls_list)

    def FetchAllVariables(self, graph, variables_context):
        print("Sparql_CIM_Process.FetchAllVariables variables_context=", variables_context)
        properties_tuple, url_nodes_list = self.GetListOfOntologyProperties(variables_context)

        returned_variables = {}

        if isinstance(url_nodes_list, list) and len(url_nodes_list) == 0:
            print("FetchAllVariables No such process with self.m_properties:", self.m_properties)
            # No such process.
            return returned_variables

        # If no process was found with the properties, try with the associator.
        if associator_CIM_ProcessExecutable in self.m_associators:
            associated_instance = self.m_associators[associator_CIM_ProcessExecutable]
            if associated_instance.m_variable in variables_context:
                if url_nodes_list is not None:
                    raise Exception("BUG: Contradiction with non-empty processe list")
                node_uri_refs_list = self.GetProcessesFromExecutable(graph, variables_context)
                returned_variables[self.m_variable] = node_uri_refs_list
                return returned_variables

        if not url_nodes_list:
            # Get all objects by default.
            properties_tuple, url_nodes_list = self.GetAllObjects()

        # The object creation has evaluated properties of these objects.
        # Some of these properties might be mapped to variables which are not in used yet.
        # Their values must be returned, so they will be part of the next variables contexts.
        assert isinstance(url_nodes_list, list)
        properties_indices = []
        for index_property, one_property in enumerate(properties_tuple):
            # Maybe this property is defined in the generated objects but not in the instance.
            if one_property in self.m_properties:
                prop_value = self.m_properties[one_property]
                if isinstance(prop_value, rdflib.term.Variable) and prop_value not in variables_context:
                    properties_indices.append(index_property)
        new_properties_tuple = tuple(self.m_properties[properties_tuple[index_property]] for index_property in properties_indices)
        new_values_list = [tuple(value_tuple[index_property] for index_property in properties_indices) for value_tuple in url_nodes_list]
        if properties_indices:
            returned_variables[new_properties_tuple] = new_values_list


        node_uri_refs_list = []

        for values_tuple in url_nodes_list:
            assert len(values_tuple) == len(properties_tuple)
            properties_dict = dict(zip(properties_tuple, values_tuple))
            node_uri_ref = self.CreateURIRef(graph, "CIM_Process", class_CIM_Process, properties_dict)
            node_uri_refs_list.append(node_uri_ref)

            process_id = int(properties_dict[predicate_Handle])
            self.DefineExecutableFromProcess(variables_context, process_id, graph, returned_variables, node_uri_ref)

        assert isinstance(self.m_variable, rdflib.term.Variable)
        assert self.m_variable not in returned_variables
        returned_variables[self.m_variable] = node_uri_refs_list
        return returned_variables

def CreateSparql_CIM_Object(class_name, the_subject):
    class_name_to_class = {
        "CIM_DataFile":Sparql_CIM_DataFile,
        "CIM_Directory": Sparql_CIM_Directory,
        "CIM_Process": Sparql_CIM_Process,
    }

    the_class = class_name_to_class[class_name]
    the_instance = the_class(class_name, the_subject)
    return the_instance

################################################################################

# This takes the list of triples extracted from the Sparql query,
# and returns a list of instances of CIM classes, each of them
# containing the triples using its instances. The association is
# done based on the variable representing the instance.
# There might be several instances of the same class.
def part_triples_to_instances_dict_function(part):
    instances_dict = dict()
    for part_subject, part_predicate, part_object in part.triples:
        #print("    ", part_subject, part_predicate, part_object)
        if part_predicate == rdflib.namespace.RDF.type:
            if isinstance(part_subject, rdflib.term.Variable):
                class_as_str = part_object.toPython()
                class_short = class_as_str[len(survol_url):]
                if class_as_str.startswith(survol_url):
                    instances_dict[part_subject] = CreateSparql_CIM_Object(class_short, part_subject)

    print("Created instances:", instances_dict.keys())

    for part_subject, part_predicate, part_object in part.triples:
        current_instance = instances_dict.get(part_subject, None)
        if not current_instance: continue
        assert isinstance(current_instance, Sparql_CIM_Object)
        if part_predicate == rdflib.namespace.RDF.type: continue

        if part_predicate == rdflib.namespace.RDFS.seeAlso: continue

        associator_instance = instances_dict.get(part_object, None)
        if associator_instance:
            assert isinstance(associator_instance, Sparql_CIM_Object)
            current_instance.m_associators[part_predicate] = associator_instance
            associator_instance.m_associated[part_predicate] = current_instance
        else:
            assert isinstance(part_object, (rdflib.term.Literal, rdflib.term.Variable))
            current_instance.m_properties[part_predicate] = part_object

    return instances_dict

# The input is a set of {variable: list-of-values.
# It returns a set of {variable: value}, which is the set of combinations
#of all possible values for each variable.
# A variable can also be a tuple of rdflib variables.
# In this case, the values must also be tuples.
def product_variables_lists(returned_variables, iter_keys = None):
    try:
        if not iter_keys:
            iter_keys = iter(returned_variables.items())
        key, values_list = next(iter_keys)
        assert isinstance(values_list, list)

        for one_dict in product_variables_lists(returned_variables, iter_keys):
            for one_value in values_list:
                new_dict = one_dict.copy()
                if isinstance(key, tuple):
                    # Maybe, several correlated variables.
                    assert isinstance(one_value, tuple) and len(key) == len(one_value)
                    # Each key is a tuple of variable matched by each of the tuples of the list of values.
                    assert all((isinstance(single_key, rdflib.term.Variable) for single_key in key))
                    assert all((isinstance(single_value, (rdflib.term.Literal, rdflib.term.URIRef)) for single_value in one_value))
                    sub_dict = dict(zip(key, one_value))
                    new_dict.update(sub_dict)
                else:
                    assert isinstance(key, rdflib.term.Variable)
                    assert isinstance(one_value, (rdflib.term.Literal, rdflib.term.URIRef))
                    new_dict[key] = one_value
                yield new_dict
    except StopIteration:
        yield {}

# An instance which is completely known and can be used as a starting point.
def findable_instance_key(instances_dict):
    print("findable_instance_key")
    for instance_key, one_instance in instances_dict.items():
        one_instance.CalculateVariablesNumber()
        print("    Key=", instance_key, "Instance=", one_instance)
        # Maybe we could return the instance with the greatest number of
        # literals ? Or the one whose implied instances are the fastest to find.
        # if one_instance.m_number_variables == 0 and one_instance.m_number_literals > 0:

        # We want to be able to retrieve at least one object, and as fast as possible.
        # This should check if wthe properties of the ontology are defined,
        # this is very important for WMI otherwise the performance can be awful.
        # On the other hand, in the general case, any property is enough, maybe none of them.
        # Realistically, in this examples, the ontologies properties are required.
        if one_instance.m_number_literals > 0:
            return instance_key

    # Could not find an instance with enough information.
    # The only possibility is to list all object. So, return the first instance.
    for instance_key, one_instance in instances_dict.items():
        return instance_key

# Exploration of the graph, starting by the ones which can be calculated without inference.
def visit_all_nodes(instances_dict):
    # Find a string point to walk the entire graph.
    start_instance_key = findable_instance_key(instances_dict)
    start_instance = instances_dict[start_instance_key]

    for instance_key, one_instance in instances_dict.items():
        one_instance.m_visited = False

    visited_instances = []
    unvisited_instances = set([one_instance for one_instance in instances_dict.values()])

    def instance_recursive_visit(one_instance):
        assert isinstance(one_instance, Sparql_CIM_Object)
        one_instance.m_visited = True
        visited_instances.append(one_instance)
        unvisited_instances.remove(one_instance)
        for sub_instance in one_instance.m_associators.values():
            if not sub_instance.m_visited:
                instance_recursive_visit(sub_instance)
        for sub_instance in one_instance.m_associated.values():
            if not sub_instance.m_visited:
                instance_recursive_visit(sub_instance)

        # The input instance is known if and only if it is possible
        # to give a value to all the variables it may contain.
        # If not all of them are known, too many values might be produced,
        # the extreme case being to return all possible instances of a class.
        # TODO: The right thing is to walk the graph is incrementally aggregate
        # TODO: the list of known variables, choosing as next node, the ones
        # TODO: using these variables and no other, preferably.
        # FIXME: If some nodes are not viisted, just append them.

    instance_recursive_visit(start_instance)

    def get_property_variables_list(one_instance):
        return set([property_value
                    for property_value in one_instance.m_properties.values()
                    if isinstance(property_value, rdflib.term.Variable)])

    assert len(visited_instances) + len(unvisited_instances) == len(instances_dict)
    all_properties_set = set.union(*[get_property_variables_list(one_instance) for one_instance in visited_instances])

    while True:
        closest_properties_set = None
        biggest_intersection_num = 0
        best_instance = None
        for sub_instance in unvisited_instances:
            sub_property_variables = get_property_variables_list(sub_instance)
            properties_intersection = all_properties_set.intersection(sub_property_variables)
            num_intersection = len(properties_intersection)
            if num_intersection >= biggest_intersection_num:
                biggest_intersection_num = num_intersection
                best_instance = sub_instance
                closest_properties_set = sub_property_variables
        if not best_instance:
            break
        all_properties_set.update(closest_properties_set)
        instance_recursive_visit(best_instance)

    if len(unvisited_instances) > 0:
        visited_instances += unvisited_instances
        WARNING("visit_all_nodes len(unvisited_instances)=%d", len(unvisited_instances))
    assert len(visited_instances) == len(instances_dict)
    return visited_instances


# Inspired from https://rdflib.readthedocs.io/en/stable/_modules/examples/custom_eval.html
def custom_eval_function(ctx, part):
    # part.name = "SelectQuery", "Project", "BGP"
    if part.name == 'BGP':
        add_ontology(ctx.graph)

        print("Instances:")
        instances_dict = part_triples_to_instances_dict_function(part)
        print("Instance before sort", len(instances_dict))
        for instance_key, one_instance in instances_dict.items():
            print("    Key=", instance_key, "Instance=", one_instance)

        visited_nodes = visit_all_nodes(instances_dict)
        assert len(instances_dict) == len(visited_nodes)
        print("GRAPH VISIT:", len(visited_nodes))
        for one_instance in visited_nodes:
            print("    Instance=", one_instance)


        # This is a dictionary of variables.
        variables_context = {}

        def recursive_instantiation(instance_index):
            if instance_index == len(visited_nodes):
                return
            margin = " " + str(instance_index) + "    " * (instance_index + 1)
            print("recursive_instantiation: ix=", instance_index,
                  "visited nodes=", [nod.m_variable for nod in visited_nodes])

            # This returns the first instance which is completely kown, i.e. its parameters
            # are iterals, or variables whose values are known in the current context.
            one_instance = visited_nodes[instance_index]
            print(margin + "one_instance=", one_instance)
            returned_variables = one_instance.FetchAllVariables(ctx.graph, variables_context)

            print(margin + "returned_variables=", returned_variables)

            for one_subset in product_variables_lists(returned_variables):
                variables_context.update(one_subset)
                recursive_instantiation(instance_index+1)

        recursive_instantiation(0)

        INFO("Graph after recursive_instantiation: %d triples", len(ctx.graph))
        # for s,p,o in ctx.graph:
        #     print("   ", s, p, o)

        # <type 'generator'>
        ret_BGP = rdflib.plugins.sparql.evaluate.evalBGP(ctx, part.triples)
        return ret_BGP

    raise NotImplementedError()
