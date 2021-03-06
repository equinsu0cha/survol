#!/usr/bin/env python

# Many SPARQL examples.
# http://api.talis.com/stores/space/items/tutorial/spared.html?query=SELECT+%3Fp+%3Fo%0D%0A{+%0D%0A++%3Chttp%3A%2F%2Fnasa.dataincubator.org%2Fspacecraft%2F1968-089A%3E+%3Fp+%3Fo%0D%0A}
#
# This is equivalent to:
# Special characters encoded in hexadecimal.
#
# The goal is to extract triples, for two different purposes:
# (1) Transform a Sparql query into WQL: This might work in very simple cases;, for WMI and WBEM.
# (2) Or identify which scripts should be run to feed a local triplestore and get useful data.
# Both purposes need the triples and the classes.

from __future__ import print_function

import os
import sys
import json
import unittest
import pkgutil
import rdflib

from init import *

update_test_path()

import lib_sparql
import lib_util
import lib_common
import lib_properties
import lib_kbase
import lib_wmi
import lib_sparql_custom_evals

# This can run only on Windows.
def setUpModule():
    try:
        import wmi
    except ImportError as err:
        raise unittest.SkipTest(str(err))

################################################################################

survol_namespace = rdflib.Namespace(lib_sparql_custom_evals.survol_url)

################################################################################

class SparqlWmiBasicTest(unittest.TestCase):
    def test_wmi_instance(self):
        the_instance = lib_sparql_custom_evals.Sparql_WMI_GenericObject("CIM_Process", rdflib.Variable("the_var"))
        the_instance.m_properties["Handle"] = "123"
        as_str = str(the_instance)
        self.assertTrue(as_str == "Sparql_CIM_Object:CIM_Process:the_var:=123")

################################################################################

class CUSTOM_EVALS_WMI_Base_Test(unittest.TestCase):
    """
    This sets the CUSTOM_EVALS callback for all derived tests.
    This callbask analyses the SPARQL query statements and loads the RDF triples
    from WMI data, by splitting the SPARQL query into nested WQL queries.
    """

    def setUp(self):
        # add function directly, normally we would use setuptools and entry_points
        rdflib.plugins.sparql.CUSTOM_EVALS['custom_eval_function_wmi'] = lib_sparql_custom_evals.custom_eval_function_wmi

    def tearDown(self):
        if 'custom_eval_function_wmi' in rdflib.plugins.sparql.CUSTOM_EVALS:
            del rdflib.plugins.sparql.CUSTOM_EVALS['custom_eval_function_wmi']



################################################################################


class SparqlWmiFromPropertiesTest(CUSTOM_EVALS_WMI_Base_Test):

    def test_wmi_query_process(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc survol:Handle '%d'  .
              ?url_proc rdf:type survol:CIM_Process .
            }""" % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = rdflib_graph.query(sparql_query)
        print("query_result=", query_result, len(query_result))
        for s_p_o in query_result:
            print("    ", s_p_o)
        self.assertTrue( len(query_result) == 1)

        process_node = lib_common.gUriGen.UriMakeFromDict("CIM_Process", {"Handle": CurrentPid})
        print("Expected process_node=", process_node)
        self.assertTrue(process_node == list(query_result)[0][0])

    def test_wmi_query_directory(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_dir
            WHERE
            { ?url_dir survol:Name "C:"  .
              ?url_dir rdf:type survol:CIM_Directory .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("query_result=", query_result, len(query_result))
        directory_node = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": "C:"})
        self.assertEqual(directory_node, query_result[0][0])

    def test_wmi_query_directory_caption(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?caption_dir
            WHERE
            { ?url_dir survol:Name "C:"  .
              ?url_dir survol:Caption ?caption_dir  .
              ?url_dir rdf:type survol:CIM_Directory .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("query_result=", query_result, len(query_result))

        # FIXME: No explanation yet for this difference.
        c_disk_name = "C:" if is_windows10 and not is_travis_machine() else "c:"
        self.assertEqual(str(query_result[0][0]), c_disk_name)

    def test_Win32_LogicalDisk_C(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_disk
            WHERE
            { ?url_disk rdf:type survol:Win32_LogicalDisk .
              ?url_disk survol:DeviceID "C:" .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        directory_node = lib_common.gUriGen.UriMakeFromDict("Win32_LogicalDisk", {"DeviceID": "C:"})
        self.assertEqual(directory_node, query_result[0][0])

    def test_Win32_LogicalDisk_all(self):
        "Load all disks."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_disk
            WHERE
            { ?url_disk rdf:type survol:Win32_LogicalDisk .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        directory_node = lib_common.gUriGen.UriMakeFromDict("Win32_LogicalDisk", {"DeviceID": "C:"})
        self.assertTrue(directory_node in [one_query[0] for one_query in query_result])

    def test_wmi_query_user_account_url(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_account
            WHERE
            { ?url_account rdf:type survol:Win32_UserAccount .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        # At least two users: "Administrator" and curret user.
        self.assertTrue(len(query_result) >= 2)

    def test_wmi_query_user_account(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?account_name ?account_domain
            WHERE
            { ?url_account rdf:type survol:Win32_UserAccount .
              ?url_account survol:Name ?account_name .
              ?url_account survol:Domain ?account_domain .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        # Result= [
        # (rdflib.term.Literal(u'Administrator'), rdflib.term.Literal(u'rchateau-HP')),
        # (rdflib.term.Literal(u'HomeGroupUser$'), rdflib.term.Literal(u'rchateau-HP')),
        # (rdflib.term.Literal(u'Guest'), rdflib.term.Literal(u'rchateau-HP')),
        # (rdflib.term.Literal(u'rchateau'), rdflib.term.Literal(u'rchateau-HP'))]
        only_names = [str(one_result[0]) for one_result in query_result]
        print("only_names=", only_names)
        self.assertTrue("Administrator" in only_names)
        self.assertTrue("Guest" in only_names)
        self.assertTrue(CurrentUsername in only_names)

        for one_result in query_result:
            # Problem on Travis: Domain = 'PACKER-5D93E860', machine='packer-5d93e860-43ba-c2e7-85d2-3ea0696b8fc8'
            self.assertTrue(str(one_result[1]).lower() ==  CurrentDomainWin32)

    def test_CIM_Process_Name(self):
        sparql_query="""
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc rdf:type survol:CIM_Process .
              ?url_proc survol:Name "python.exe" .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        # At least one process running Python, i.e. the current process.
        self.assertTrue(len(query_result) > 0)

    def test_CIM_Process_Name_to_Pid(self):
        sparql_query="""
            PREFIX survol: <%s>
            SELECT ?pid_proc
            WHERE
            { ?url_proc rdf:type survol:CIM_Process .
              ?url_proc survol:Name "python.exe" .
              ?url_proc survol:Handle ?pid_proc .
            }""" % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        # At least one process running Python, i.e. the current process.
        self.assertTrue(len(query_result) > 0)
        only_pids = [str(one_result[0]) for one_result in query_result]
        print("only_pids=", only_pids)
        self.assertTrue(str(CurrentPid) in only_pids)

    def test_Win32_Process_Description_to_Pid(self):
        sparql_query = """
            PREFIX survol: <%s>
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?pid
            WHERE
            {
                ?url_proc rdf:type survol:Win32_Process .
                ?url_proc survol:Description 'python.exe' .
                ?url_proc survol:Handle ?pid .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        self.assertTrue(len(query_result) > 0)
        only_pids = [str(one_result[0]) for one_result in query_result]
        print("only_pids=", only_pids)
        self.assertTrue(str(CurrentPid) in only_pids)

    def test_Win32_Process_Pid_to_ParentPid(self):
        sparql_query = """
            PREFIX survol: <%s>
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?parent_pid
            WHERE
            {
                ?url_proc rdf:type survol:Win32_Process .
                ?url_proc survol:ParentProcessId ?parent_pid .
                ?url_proc survol:Handle '%d' .
            }""" % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(len(query_result), 1)
        only_parent_pids = [str(one_result[0]) for one_result in query_result]
        self.assertEqual(str(CurrentParentPid), only_parent_pids[0])

    def test_Win32_Process_Pid_to_ParentProcess(self):
        sparql_query = """
            PREFIX survol: <%s>
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?parent_description
            WHERE
            {
                ?url_proc rdf:type survol:Win32_Process .
                ?url_proc survol:ParentProcessId ?parent_pid .
                ?url_proc survol:Handle '%d' .
                ?url_parent_proc rdf:type survol:Win32_Process .
                ?url_parent_proc survol:Description ?parent_description .
                ?url_parent_proc survol:Handle ?parent_pid .
            }""" % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(len(query_result), 1)
        only_descriptions = [str(one_result[0]) for one_result in query_result]
        # Depending on the test framework, Description='pycharm64.exe' for example.
        print("Description=%s", only_descriptions[0])

    def test_Win32_Process_ParentPid_to_Pid(self):
        sparql_query = """
            PREFIX survol: <%s>
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?pid
            WHERE
            {
                ?url_proc rdf:type survol:Win32_Process .
                ?url_proc survol:ParentProcessId '%d' .
                ?url_proc survol:Handle ?pid .
            }""" % (survol_namespace, CurrentParentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        self.assertTrue(len(query_result) >= 1)
        only_pids = [str(one_result[0]) for one_result in query_result]
        print("CurrentPid=", CurrentPid)
        print("only_pids=", only_pids)
        self.assertTrue(str(CurrentPid) in only_pids)

    def test_Win32_Process_Pid_to_ParentPid_to_Children(self):
        sparql_query = """
            PREFIX survol: <%s>
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?parent_children_pid
            WHERE
            {
                ?url_proc rdf:type survol:Win32_Process .
                ?url_proc survol:ParentProcessId ?parent_pid .
                ?url_proc survol:Handle '%d' .
                ?url_parent_proc rdf:type survol:Win32_Process .
                ?url_parent_proc survol:Handle ?parent_pid .
                ?url_parent_proc_children rdf:type survol:Win32_Process .
                ?url_parent_proc_children survol:ParentProcessId ?parent_pid .
                ?url_parent_proc_children survol:Handle ?parent_children_pid .
            }""" % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        self.assertTrue(len(query_result) >= 1)
        only_pids = [str(one_result[0]) for one_result in query_result]
        print("only_pids=", sorted(only_pids))
        self.assertTrue(str(CurrentPid) in only_pids)

    def test_Win32_Process_all(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?pid WHERE {
                ?url_process a survol:Win32_Process .
                ?url_process survol:Handle ?pid .
            }
        """ % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        only_pids = [str(one_result[0]) for one_result in query_result]
        print("only_pids=", only_pids)
        self.assertTrue(str(CurrentPid) in only_pids)

    def test_select_Win32_Process_siblings(self):
        """Win32_Process.ParentProcessId is defined."""
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?sibling_pid
            WHERE
            { ?url_proc_current survol:Handle '%d' .
              ?url_proc_current rdf:type survol:Win32_Process .
              ?url_proc_sibling rdf:type survol:Win32_Process .
              ?url_proc_sibling survol:Handle ?sibling_pid .
              ?url_proc_parent rdf:type survol:Win32_Process .
              ?url_proc_parent survol:Handle ?parent_pid .
              ?url_proc_current survol:ParentProcessId ?parent_pid .
              ?url_proc_sibling survol:ParentProcessId ?parent_pid .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        actual_sibling_pids = set([int(str(one_tuple[0])) for one_tuple in query_result])

        # Comparaison with the list of sub-processes of the current one.
        expected_sibling_pids = set([proc.pid for proc in psutil.Process(CurrentParentPid).children(recursive=False)])
        print("expected_sibling_pids=", expected_sibling_pids)

        self.assertEqual(expected_sibling_pids, actual_sibling_pids)

    def test_select_CIM_DiskDrive(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_disk
            WHERE
            { ?url_disk rdf:type survol:CIM_DiskDrive .
            }
        """ % survol_namespace
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_CIM_DataFile_Name(self):
        file_name = lib_util.standardized_file_path(always_present_file)
        sparql_query="""
            PREFIX survol: <%s>
            SELECT ?url_file
            WHERE
            {
              ?url_file survol:Name "%s" .
              ?url_file rdf:type survol:CIM_DataFile .
            }""" % (survol_namespace, file_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(len(query_result), 1)
        datafile_node = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name})
        self.assertEqual(query_result[0][0], datafile_node)

    def test_CIM_Directory_Name(self):
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query="""
            PREFIX survol: <%s>
            SELECT ?url_file
            WHERE
            {
              ?url_file survol:Name "%s" .
              ?url_file rdf:type survol:CIM_Directory .
            }""" % (survol_namespace, directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(len(query_result), 1)
        directory_node = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": directory_name})
        self.assertEqual(query_result[0][0], directory_node)

    def test_Win32_UserAccount_to_caption(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?caption
            WHERE
            {
                ?url_user rdf:type survol:Win32_UserAccount .
                ?url_user survol:Name '%s' .
                ?url_user survol:Caption ?caption .
            }""" % (survol_namespace, CurrentUsername)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        # On Travis: 'PACKER-5D93E860\\\\travis'
        self.assertEqual(len(query_result), 1)
        account_caption = str(query_result[0][0])
        expected_caption = CurrentDomainWin32.lower() + "\\\\" + CurrentUsername
        print("account_caption=", account_caption)
        print("expected_caption=", expected_caption)
        self.assertEqual(account_caption.lower(), expected_caption)

    def test_Win32_UserAccount_to_domain_caption(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?domain ?caption
            WHERE
            {
                ?url_user rdf:type survol:Win32_UserAccount .
                ?url_user survol:Name '%s' .
                ?url_user survol:Caption ?caption .
                ?url_user survol:Domain ?domain .
            }""" % (survol_namespace, CurrentUsername)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        # [(rdflib.term.Literal(u'rchateau-HP'), rdflib.term.Literal(u'rchateau-HP\\\\rchateau'))]
        print("Result=", query_result)
        self.assertTrue(len(query_result)== 1)
        account_domain = str(query_result[0][0])
        account_caption = str(query_result[0][1])
        self.assertEqual(account_domain.lower(), CurrentDomainWin32)
        self.assertEqual(account_caption.lower(), CurrentDomainWin32 + "\\\\" + CurrentUsername)



class SparqlWmiAssociatorsTest(CUSTOM_EVALS_WMI_Base_Test):

    # We must anyway give the type of url_file,
    # otherwise we cannot deduce that it is an associator.
    def test_associator_Win32_Process_executable_node(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_file
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:CIM_ProcessExecutable ?url_file .
              ?url_proc rdf:type survol:Win32_Process .
              ?url_file rdf:type survol:CIM_DataFile .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        query_str_only = set([str(one_query[0]) for one_query in query_result])
        print("query_str_only=", query_str_only)

        file_name_python_exe = lib_util.standardized_file_path(sys.executable)
        node_python_exe = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name_python_exe})
        print("node_python_exe=", node_python_exe)
        self.assertTrue(str(node_python_exe) in query_str_only)

        # u'http://rchateau-hp:80/LocalExecution/entity.py?xid=CIM_DataFile.Name=c:/windows/system32/iphlpapi.dll' etc
        file_name_gdi32 = lib_util.standardized_file_path("c:/windows/system32/gdi32.dll")
        datafile_node_gdi32 = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name_gdi32})
        self.assertTrue(str(datafile_node_gdi32) in query_str_only)

    def test_associator_CIM_Process_executable_node(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_file
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:CIM_ProcessExecutable ?url_file .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_file rdf:type survol:CIM_DataFile .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))

        filenames_only = set(str(one_result[0]) for one_result in query_result)
        print("filenames_only=", filenames_only)

        file_name_python_exe = lib_util.standardized_file_path(sys.executable)
        node_python_exe = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name_python_exe})
        print("node_python_exe=", node_python_exe)
        self.assertTrue(str(node_python_exe) in filenames_only)

        file_name_ntdll = lib_util.standardized_file_path("c:/windows/system32/ntdll.dll")
        datafile_node_ntdll = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name_ntdll})
        self.assertTrue(str(datafile_node_ntdll) in filenames_only)

    def test_associator_CIM_Process_executable_name(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?exec_filepath
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:CIM_ProcessExecutable ?url_file .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_file rdf:type survol:CIM_DataFile .
              ?url_file survol:Name ?exec_filepath.
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        filenames_only = set([str(one_result[0]) for one_result in query_result])
        print("filenames_only=", filenames_only)

        file_name_python_exe = lib_util.standardized_file_path(sys.executable)
        self.assertTrue(file_name_python_exe in filenames_only)

        file_name_ntdll = lib_util.standardized_file_path("c:/windows/system32/ntdll.dll")
        self.assertTrue(file_name_ntdll in filenames_only)

    def test_select_Win32_Process_siblings_executables(self):
        """Finds the names of the executables run by the sibling processes of the current one,
        i.e. with the same parent process."""
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_execfile_sibling
            WHERE
            { ?url_proc_current survol:Handle '%d' .
              ?url_proc_current rdf:type survol:Win32_Process .
              ?url_proc_sibling rdf:type survol:Win32_Process .
              ?url_proc_parent rdf:type survol:Win32_Process .
              ?url_proc_parent survol:Handle ?parent_pid .
              ?url_proc_current survol:ParentProcessId ?parent_pid .
              ?url_proc_sibling survol:ParentProcessId ?parent_pid .
              ?url_proc_sibling survol:CIM_ProcessExecutable ?url_execfile_sibling .
              ?url_execfile_sibling rdf:type survol:CIM_DataFile .
              ?url_execfile_sibling survol:Name ?name_execfile_sibling .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("query_result=", query_result)
        actual_sibling_dlls_exes = [str(one_tuple[0]) for one_tuple in query_result]
        print("actual_sibling_dlls_exes=", actual_sibling_dlls_exes)

        expected_sibling_exes = set([
            lib_util.standardized_file_path(proc.exe())
            for proc in psutil.Process(CurrentParentPid).children(recursive=False)])
        print("expected_sibling_exes=", expected_sibling_exes)

        self.assertTrue(expected_sibling_exes.issubset(actual_sibling_dlls_exes))

    def test_select_Win32_Process_children_executables_names(self):
        """Win32_Process.ParentProcessId is defined."""
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_execfile_child
            WHERE
            { ?url_proc_child rdf:type survol:Win32_Process .
              ?url_proc_child survol:ParentProcessId '%d' .
              ?url_proc_child survol:CIM_ProcessExecutable ?url_execfile_child .
              ?url_execfile_child rdf:type survol:CIM_DataFile .
              ?url_execfile_child survol:Name ?name_execfile_child .
            }""" % (survol_namespace, CurrentParentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("query_result=", query_result)
        actual_sibling_dlls_exes = set(str(one_tuple[0]) for one_tuple in query_result)
        print("actual_sibling_dlls_exes=", actual_sibling_dlls_exes)

        expected_sibling_exes = set(
            lib_util.standardized_file_path(proc.exe())
            for proc in psutil.Process(CurrentParentPid).children(recursive=False))
        print("expected_sibling_exes=", expected_sibling_exes)

        self.assertTrue(expected_sibling_exes.issubset(actual_sibling_dlls_exes))

    def test_select_Win32_Process_children_executables_nodes(self):
        """Win32_Process.ParentProcessId is defined."""
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_execfile_child
            WHERE
            { ?url_proc_child rdf:type survol:Win32_Process .
              ?url_proc_child survol:ParentProcessId '%d' .
              ?url_proc_child survol:CIM_ProcessExecutable ?url_execfile_child .
              ?url_execfile_child rdf:type survol:CIM_DataFile .
            }""" % (survol_namespace, CurrentParentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("query_result=", query_result)

        expected_sibling_exe_names = [
            lib_util.standardized_file_path(proc.exe())
            for proc in psutil.Process(CurrentParentPid).children(recursive=False)]
        print("expected_sibling_exe_names=", expected_sibling_exe_names)
        expected_sibling_exe_nodes = set(
            lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": exe_name})
            for exe_name in expected_sibling_exe_names)
        print("expected_sibling_exe_nodes=", expected_sibling_exe_nodes)

        actual_sibling_exe_nodes = set(result_tuple[0] for result_tuple in query_result)
        print("actual_sibling_exe_nodes=", actual_sibling_exe_nodes)

        assert expected_sibling_exe_nodes.issubset(actual_sibling_exe_nodes)

    def test_associator_CIM_Process_executable_directory_to_name(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?exec_dirpath
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:CIM_ProcessExecutable ?url_execfile .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_execfile rdf:type survol:CIM_DataFile .
              ?url_execfile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Name ?exec_dirpath .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        dirnames_only = set([str(one_result[0]) for one_result in query_result])
        print("dirnames_only=", dirnames_only)

        executable_dirname = lib_util.standardized_file_path(os.path.dirname(CurrentExecutable))
        print("executable_dirname=", executable_dirname)

        self.assertTrue(executable_dirname in dirnames_only)

    def test_associator_CIM_Process_executable_to_directory_node(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:CIM_ProcessExecutable ?url_execfile .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_execfile rdf:type survol:CIM_DataFile .
              ?url_execfile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        dirnodes_only = {str(one_result[0]) for one_result in query_result}
        print("dirnodes_only=", dirnodes_only, "len=", len(dirnodes_only))

        current_executable_dir = os.path.dirname(CurrentExecutable)
        for dir_path in [
            current_executable_dir,
            current_executable_dir + "/lib/site-packages/win32",
            current_executable_dir + "/lib/site-packages/psutil",
            current_executable_dir + "/dlls",
            "c:/windows/system32",
            "c:/windows/system32/wbem"]:
            standard_dir_path = lib_util.standardized_file_path(dir_path)
            node_dir = str(lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": standard_dir_path}))
            print("Path=", dir_path)
            print("Node=", node_dir)
            self.assertTrue(node_dir in dirnodes_only)

    def test_associator_CIM_Process_to_computer_node(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_computer
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:Win32_SystemProcesses ?url_computer .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_computer rdf:type survol:Win32_ComputerSystem .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        computer_node = lib_common.gUriGen.UriMakeFromDict("Win32_ComputerSystem", {"Name": CurrentDomainWin32.upper()})
        print("computer_node=", computer_node)

        self.assertTrue(computer_node == query_result[0][0])

    def test_associator_CIM_Process_to_computer_name(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?computer_name
            WHERE
            { ?url_proc survol:Handle '%d' .
              ?url_proc survol:Win32_SystemProcesses ?url_computer .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_computer rdf:type survol:Win32_ComputerSystem .
              ?url_computer survol:Name ?computer_name .
            }""" % (survol_namespace, CurrentPid)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertTrue(CurrentDomainWin32.upper() == str(query_result[0][0]))

    def test_associator_computer_node_from_name(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_computer
            WHERE
            { ?url_computer rdf:type survol:Win32_ComputerSystem .
              ?url_computer survol:Name "%s" .
            }""" % (survol_namespace, CurrentDomainWin32.upper())

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        computer_node = lib_common.gUriGen.UriMakeFromDict("Win32_ComputerSystem", {"Name": CurrentDomainWin32.upper()})
        self.assertTrue([(computer_node,)] == query_result)

    def test_associator_computer_name_to_CIM_Process_ids(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?process_id
            WHERE
            { ?url_proc survol:Handle ?process_id .
              ?url_proc survol:Win32_SystemProcesses ?url_computer .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_computer rdf:type survol:Win32_ComputerSystem .
              ?url_computer survol:Name "%s" .
            }""" % (survol_namespace, CurrentDomainWin32.upper())

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        pids_only = [int(str(one_tuple[0])) for one_tuple in query_result]
        print("pids_only=", pids_only)
        self.assertTrue(CurrentPid in pids_only)
        self.assertTrue(CurrentParentPid in pids_only)

    def test_associator_computer_name_to_process_executable(self):
        """This displays the executables of all processes on this machine."""
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_file
            WHERE
            { ?url_proc survol:Win32_SystemProcesses ?url_computer .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_proc survol:CIM_ProcessExecutable ?url_file .
              ?url_file rdf:type survol:CIM_DataFile .
              ?url_computer rdf:type survol:Win32_ComputerSystem .
              ?url_computer survol:Name "%s" .
            }""" % (survol_namespace, CurrentDomainWin32.upper())

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        query_as_str = set([str(one_result[0]) for one_result in query_result])
        print("query_as_str=", query_as_str)

        # These files must be there because they are used by the current process.
        mandatory_file_paths = [
            sys.executable,
            "c:/windows/system32/shell32.dll",
            "c:/windows/system32/ole32.dll",
            "c:/windows/system32/oleaut32.dll",
            "c:/windows/system32/gdi32.dll"
        ]
        for one_path in mandatory_file_paths:
            standard_path = lib_util.standardized_file_path(one_path)
            node_file = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": standard_path})
            print("standard_path=", standard_path)
            self.assertTrue(str(node_file) in query_as_str)
        print("Number of files:", len(query_as_str))

    def test_associator_executable_name_to_process(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?process_id
            WHERE
            { ?url_proc survol:Handle ?process_id .
              ?url_proc survol:CIM_ProcessExecutable ?url_file .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_file rdf:type survol:CIM_DataFile .
              ?url_file survol:Name "%s" .
            }""" % (survol_namespace, CurrentExecutable)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        pids_only = [int(str(pid_literal_tuple[0])) for pid_literal_tuple in query_result]
        print("pids_only=", pids_only)
        self.assertTrue(CurrentPid in pids_only)

    ################################################################################

    def test_associator_directory_to_datafile_nodes(self):
        """All the file nodes in a directory."""
        file_name = lib_util.standardized_file_path(always_present_file)
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_datafile
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Name "%s" .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
            }""" % (survol_namespace, directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))

        query_urls = [str(one_tuple[0]) for one_tuple in query_result]
        print("query_urls=", query_urls)

        # ASSOCIATOR INVERSION !!!!!!!!!!

        node_url = lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": file_name})
        node_file_name = str(node_url)
        print("node_file_name=", node_file_name)
        self.assertTrue(node_file_name in query_urls)

    def test_associator_directory_to_datafile_names(self):
        """All the file names in a directory."""
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_datafile
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_datafile survol:Name ?name_datafile .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Name "%s" .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
            }""" % (survol_namespace, directory_name)

        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        filenames_only = set([str(one_result[0]) for one_result in query_result])
        print("filenames_only=%s\n" % filenames_only)

        for dir_root, dir_dirs, dir_files in os.walk(directory_name):
            expected_files = set(
                # File path is standardized, because it is mistakenly
                # converted on some versions of Windows and Python and maybe WMI parameters.
                lib_util.standardized_file_path(os.path.join(dir_root, one_file))
                for one_file in dir_files)
            break
        print("expected_files=%s\n" % expected_files)
        self.assertEqual(filenames_only, expected_files)

    def test_associator_datafile_to_directory_node(self):
        """From a file to the node of its parent directory."""
        file_name = lib_util.standardized_file_path(always_present_file)
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_datafile survol:Name "%s" .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
            }""" % (survol_namespace, file_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        # ASSOCIATOR INVERSION !!!!!!!!!!

        # The file belongs to one directory.
        self.assertEqual(len(query_result), 1)
        node_directory = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": directory_name})
        self.assertTrue((node_directory,) in query_result)

    def test_associator_directory_to_sub_directory_node(self):
        """All the subdirectories in a directory."""
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory
            WHERE
            { ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory survol:Name "%s" .
              ?url_directory_of_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Win32_SubDirectory ?url_directory_of_directory .
            }""" % (survol_namespace, directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        actual_dir_nodes = set(str(one_tuple[0]) for one_tuple in query_result)
        print("actual_dir_nodes=%s\n" % actual_dir_nodes)

        expected_dir_nodes = set()
        for dir_root, dir_dirs, dir_files in os.walk(directory_name):
            for one_dir in dir_dirs:
                dir_path = lib_util.standardized_file_path(os.path.join(dir_root, one_dir))
                dir_node = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": dir_path})
                expected_dir_nodes.add(str(dir_node))
            break
        print("expected_dir_nodes=%s\n" % expected_dir_nodes)

        self.assertEqual(actual_dir_nodes, expected_dir_nodes)

    def test_associator_sub_directory_to_directory_node(self):
        """From a subdirectory to its parent directory."""
        sub_directory_name = lib_util.standardized_file_path(always_present_sub_dir)
        directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory
            WHERE
            { ?url_sub_directory rdf:type survol:CIM_Directory .
              ?url_sub_directory survol:Name "%s" .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_sub_directory survol:Win32_SubDirectory ?url_directory .
            }""" % (survol_namespace, sub_directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        directory_node = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": directory_name})
        print("directory_node=", directory_node)
        self.assertEqual([(directory_node,)], query_result)

    def test_associator_datafile_to_directory_of_directory_node(self):
        """From a file to the node of the parent of its parent directory."""
        file_name = lib_util.standardized_file_path(always_present_sub_file)
        directory_of_directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory_of_directory
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_datafile survol:Name "%s" .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Win32_SubDirectory ?url_directory_of_directory .
            }""" % (survol_namespace, file_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        # ASSOCIATOR INVERSION !!!!!!!!!!

        # The file belongs to one directory.
        self.assertEqual(len(query_result), 1)
        node_directory_of_directory = lib_common.gUriGen.UriMakeFromDict("CIM_Directory", {"Name": directory_of_directory_name})
        self.assertEqual([(node_directory_of_directory,)], query_result)

    def test_associator_datafile_to_directory_of_directory_name(self):
        """From a file to the name of the parent of its parent directory."""
        file_name = lib_util.standardized_file_path(always_present_sub_file)
        directory_of_directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_directory_of_directory_name
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_datafile survol:Name "%s" .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory survol:Name ?url_directory_of_directory_name .
              ?url_directory survol:Win32_SubDirectory ?url_directory_of_directory .
            }""" % (survol_namespace, file_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        # The directory belongs to one directory only.
        self.assertEqual(len(query_result), 1)
        self.assertEqual(directory_of_directory_name, str(query_result[0][0]))

    def test_associator_dir_dir_to_sub_sub_datafile_node(self):
        """From a directory to the files in its subdirectories"""
        directory_of_directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_datafile
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory survol:Name "%s" .
              ?url_directory_of_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Win32_SubDirectory ?url_directory_of_directory .
            }""" % (survol_namespace, directory_of_directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        expect_filenames = [
            ["samplesubdir", "samplesubfile.txt"],
            ["samplesubdir_2", "samplesubfile_2.txt"],
        ]
        expect_pathnames = [
            lib_util.standardized_file_path(os.path.join(directory_of_directory_name, *file_name))
            for file_name in expect_filenames
        ]
        # Conversions to lowercase because of inconsistent behaviour in previous WMI and Windows versions.
        expect_nodes = sorted([
            str(lib_common.gUriGen.UriMakeFromDict("CIM_DataFile", {"Name": path_name}))
            for path_name in expect_pathnames
        ])
        print("expect_nodes=",expect_nodes)

        actual_nodes = sorted([str(one_result[0]) for one_result in query_result])
        print("actual_nodes=", actual_nodes)
        self.assertEqual(expect_nodes, actual_nodes)

    def test_associator_dir_dir_to_sub_sub_datafile_name(self):
        """From a directory to the files in its subdirectories"""
        directory_of_directory_name = lib_util.standardized_file_path(always_present_dir)
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_datafile
            WHERE
            { ?url_datafile rdf:type survol:CIM_DataFile .
              ?url_datafile survol:Name ?name_datafile .
              ?url_datafile survol:CIM_DirectoryContainsFile ?url_directory .
              ?url_directory rdf:type survol:CIM_Directory .
              ?url_directory_of_directory survol:Name "%s" .
              ?url_directory_of_directory rdf:type survol:CIM_Directory .
              ?url_directory survol:Win32_SubDirectory ?url_directory_of_directory .
            }""" % (survol_namespace, directory_of_directory_name)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

        expect_filenames = [
            ["samplesubdir", "samplesubfile.txt"],
            ["samplesubdir_2", "samplesubfile_2.txt"],
        ]
        expect_pathnames = [
            lib_util.standardized_file_path(os.path.join(directory_of_directory_name, *file_name))
            for file_name in expect_filenames
        ]
        print("expect_pathnames=",expect_pathnames)

        actual_filenames = sorted([
            lib_util.standardized_file_path(str(one_result[0]))
            for one_result in query_result])
        print("actual_filenames=", actual_filenames)
        self.assertEqual(expect_pathnames, actual_filenames)

    ################################################################################

    def test_associator_guest_user_to_groups(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_group
            WHERE
            {
                ?url_user rdf:type survol:Win32_UserAccount .
                ?url_user survol:Name 'Guest' .
                ?url_user survol:Domain ?user_domain .
                ?url_user survol:Win32_GroupUser ?url_group .
                ?url_group rdf:type survol:Win32_Group .
                ?url_group survol:Name ?name_group .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(str(query_result[0][0]), 'Guests')

    def test_associator_guests_group_to_user(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_user
            WHERE
            {
                ?url_user rdf:type survol:Win32_UserAccount .
                ?url_user survol:Name ?name_user .
                ?url_user survol:Domain ?user_domain .
                ?url_user survol:Win32_GroupUser ?url_group .
                ?url_group rdf:type survol:Win32_Group .
                ?url_group survol:Name 'Guests' .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        self.assertEqual(str(query_result[0][0]), 'Guest')

    def test_associator_computer_to_system_users(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?name_user ?domain_user
            WHERE
            {
                ?url_computer rdf:type survol:Win32_ComputerSystem .
                ?url_computer survol:Name '%s' .
                ?url_user survol:Win32_SystemUsers ?url_computer .
                ?url_user rdf:type survol:Win32_UserAccount .
                ?url_user survol:Name ?name_user .
                ?url_user survol:Domain ?domain_user .
            }""" % (survol_namespace, CurrentDomainWin32.upper())
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)
        usernames_only = [str(one_tuple[0]) for one_tuple in query_result]
        self.assertTrue('Guest' in usernames_only)
        self.assertTrue('Administrator' in usernames_only)

@unittest.skip("NOT IMPLEMENTED YET")
class SparqlSeeAlsoTest(CUSTOM_EVALS_WMI_Base_Test):
    def test_see_also_data_file(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc survol:Name "%s" .
              ?url_proc rdf:type survol:CIM_DataFile .
              ?url_proc rdfs:seeAlso "survol:CIM_DataFile/python_properties" .
            }
            """ % (survol_namespace, sys.executable)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_see_also_mapping_processes(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc survol:Name "/usr/lib/systemd/systemd-journald" .
              ?url_proc rdf:type survol:CIM_DataFile .
              ?url_proc rdfs:seeAlso "survol:CIM_DataFile/mapping_processes" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_see_also_process_handle(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc survol:Handle %d  .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_proc rdfs:seeAlso <http://vps516494.ovh.net/Survol/survol/entity.py?xid=CIM_Process.Handle=29&mode=rdf> .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_see_also_three_urls(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc
            WHERE
            { ?url_proc survol:Handle %d  .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_proc rdfs:seeAlso "survol:CIM_Process/process_open_files" .
              ?url_proc rdfs:seeAlso "survol:CIM_Process/single_pidstree" .
              ?url_proc rdfs:seeAlso "survol:CIM_Process/languages/python/current_script" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_see_also_python_properties(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc ?url_file
            WHERE
            { ?url_proc survol:Handle %d  .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_proc survol:CIM_ProcessExecutable ?url_file  .
              ?url_file rdf:type survol:CIM_DataFile .
              ?url_file rdfs:seeAlso "survol:CIM_DataFile/python_properties" .
            }
            """ % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_see_also_file_stat(self):
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_proc ?url_file
            WHERE
            { ?url_proc survol:Handle %d  .
              ?url_proc survol:CIM_ProcessExecutable ?url_file  .
              ?url_proc rdf:type survol:CIM_Process .
              ?url_file rdf:type survol:CIM_DataFile .
              ?url_file rdfs:seeAlso "survol:CIM_DataFile/file_stat" .
            }
            """ % (survol_namespace, CurrentPid)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

@unittest.skip("NOT IMPLEMENTED YET")
class SparqlMetaTest(CUSTOM_EVALS_WMI_Base_Test):

    def test_all_classes(self):
        "All WMI classes."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_class
            WHERE
            { ?url_class rdf:type rdfs:Class .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_labelled_class(self):
        "One WMI class with a given name."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_class
            WHERE
            { ?url_class rdf:type rdfs:Class .
              ?url_class rdfs:label "CIM_Process" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_all_sub_classes(self):
        # This returns all pairs of WMI classes and subclasses.
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_class ?url_subclass
            WHERE
            { ?url_subclass rdfs:subClassOf ?url_class .
              ?url_class rdf:type rdfs:Class .
              ?url_subclass rdf:type rdfs:Class .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_base_class(self):
        "This prints the base class of CIM_Process"
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_cim_process ?url_base_class
            WHERE
            { ?url_cim_process rdfs:subClassOf ?url_base_class .
              ?url_base_class rdf:type rdfs:Class .
              ?url_cim_process rdf:type rdfs:Class .
              ?url_cim_process rdfs:label "CIM_Process" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_subclasses(self):
        "This prints the derived classes of a given base class."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_class ?url_subclass
            WHERE
            { ?url_subclass rdfs:subClassOf ?url_base_class .
              ?url_base_class rdf:type rdfs:Class .
              ?url_subclass rdf:type rdfs:Class .
              ?url_base_class rdfs:label "CIM_LogicalElement" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_all_properties(self):
        "This returns all WMI properties of classes."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_attribute
            WHERE
            { ?url_attribute rdf:type rdf:Property .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_all_process_properties(self):
        "This returns all properties of the class CIM_Process."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_property
            WHERE
            { ?url_property rdf:type rdf:Property .
              ?url_property rdfs:domain survol:CIM_Process .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_all_process_named_property(self):
        "This returns the property named 'Handle' of the class CIM_Process."
        sparql_query = """
            SELECT ?url_property
            WHERE
            { ?url_property rdf:type rdf:Property .
              ?url_property rdfs:domain survol:CIM_Process .
              ?url_property rdfs:label "Handle" .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_all_process_dynamic_property(self):
        "This returns all objects with a dynamic property."
        sparql_query = """
            PREFIX survol: <%s>
            SELECT ?url_property
            WHERE
            { ?url_property rdf:type rdf:Property .
              ?url_property rdfs:domain survol:CIM_Process .
            }""" % (survol_namespace)
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    def test_server_survol_wmi_meta(self):
        sparql_query = """
            PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?url_class
            WHERE
            { ?url_class rdf:type rdfs:Class .
            }
            """
        rdflib_graph = rdflib.Graph()
        query_result = list(rdflib_graph.query(sparql_query))
        print("Result=", query_result)

    # Some query examples taken from https://codyburleson.com/sparql-examples-list-classes/
    # TODO: Test rdfs:range

################################################################################

# This works: gwmi -Query 'xxxxx'
# ASSOCIATORS OF {Win32_Process.Handle=1520}
# ASSOCIATORS OF {CIM_Process.Handle=1520}
# ASSOCIATORS OF {CIM_Process.Handle=1520} where classdefsonly
# ASSOCIATORS OF {CIM_Process.Handle=1520} where resultclass=CIM_DataFile

# For the associators, the exact keys are needed, i.e. ite object path.

if __name__ == '__main__':
    unittest.main()

# TODO: Test calls to <Any class>.AddInfo()
# TODO: When double-clicking any Python script, it should do something visible.

