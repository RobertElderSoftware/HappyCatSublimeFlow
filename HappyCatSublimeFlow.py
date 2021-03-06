import sublime, sublime_plugin
import subprocess
import os
import json
import datetime
import threading
import time
from subprocess import Popen, PIPE, STDOUT

FLOW_STATUS_BAR_KEY="flow_status_key"
highlightedRegions = {}
flowStatusRegions = []
flowRequestThreadCount = 0

class ProjectFlowStatusThread(threading.Thread):
	#  Container class to keep track of our request to the flow server for status on the entire project
	def __init__(self, cmd, edit, current_file_name):
		threading.Thread.__init__(self)
		self.cmd = cmd
		self.edit = edit
		self.current_file_name = current_file_name
	def run(self):
		p = None
		if not self.current_file_name is None:
			directory_to_check = str(os.path.dirname(self.current_file_name))
			try:
				p = Popen(["cd " + directory_to_check + " && " + sublime.load_settings('HappyCatSublimeFlow.sublime-settings').get("HappyCatSublimeFlow.FLOW_EXECUTABLE") + " status --json"], shell=True, stdout=PIPE, stdin=PIPE, stderr=STDOUT) 
				output, stderr = p.communicate()
			except Exception as e:
				print("Exception attempting to get project flow status: " + e);
			self.cmd.view.run_command('finish_flow_status_request', {'directory_checked': directory_to_check, 'result': output.decode("utf-8")})
		else:
			self.cmd.view.run_command('finish_flow_status_request', {'directory_checked': 'none', 'result': "Did not run flow command, current file name was None so how would we know what directory to run 'flow status on?'."})

def get_or_create_flow_status_window():
	#  This function will return a sublime.View object where flow error messages are printed
	#  or it will create one if none exists
	for window in sublime.windows():
		for view in window.views():
			if view.name() == sublime.load_settings('HappyCatSublimeFlow.sublime-settings').get("HappyCatSublimeFlow.FLOW_STATUS_VIEW_NAME"):
				view.set_scratch(True)
				view.set_read_only(True)
				return view
	#  Keep track of what the currently active view was, so we can switch back to
	#  it after we create the flow status window
	currently_active_view = sublime.active_window().active_view()
	new_view = sublime.active_window().new_file()
	#  Prevents being prompted when we close this view, and make it read only
	new_view.set_scratch(True)
	new_view.set_read_only(True)
	new_view.set_name(sublime.load_settings('HappyCatSublimeFlow.sublime-settings').get("HappyCatSublimeFlow.FLOW_STATUS_VIEW_NAME"))
	#  Restore active view
	sublime.active_window().focus_view(currently_active_view)
	return new_view

def plugin_loaded():
	get_or_create_flow_status_window().run_command('start_flow_status_request', {'current_file_name': sublime.active_window().active_view().file_name()})

class StatusBarProcessingAnimationThread(threading.Thread):
	#  Takes care of the animated text that appears in the status bar at
	#  the bottom while flow is processing all errors/warnings.
	def __init__(self, directory):
		threading.Thread.__init__(self)
		self.directory = directory
	def run(self):
		global flowRequestThreadCount
		animationPhases = ["███ ", "██ █", "█ ██", " ███", "█ ██", "██ █", "███ "]
		currentAnimationPhase = 0
		#  TODO:  Don't test a global variable for finished state
		while flowRequestThreadCount != 0:
			currentAnimationPhase += 1
			output = "Updating flow status: " + animationPhases[currentAnimationPhase % len(animationPhases)] + " for directory '" + self.directory + "'"
			for window in sublime.windows():
				for view in window.views():
					view.set_status(FLOW_STATUS_BAR_KEY, output)
			time.sleep(0.1)
		#  Finished processing, clear processing status (for all windows)
		for window in sublime.windows():
			for view in window.views():
				view.set_status(FLOW_STATUS_BAR_KEY, "Flow status updated: ████ for directory '" + self.directory + "'")

class CurrentFileFlowStatusThread(threading.Thread):
	#  Takes care of getting the errors and highlighted regions for a single file
	def __init__(self, cmd, edit):
		threading.Thread.__init__(self)
		self.cmd = cmd
		self.edit = edit
	def run(self):
		global highlightedRegions
		content = self.cmd.view.substr(sublime.Region(0, self.cmd.view.size()))
		p = None
		try:
			p = Popen(["cd " + str(os.path.dirname(self.cmd.view.file_name())) + " && " + sublime.load_settings('HappyCatSublimeFlow.sublime-settings').get("HappyCatSublimeFlow.FLOW_EXECUTABLE") + " check-contents --json --show-all-errors"], shell=True, stdout=PIPE, stdin=PIPE, stderr=STDOUT) 
			output, stderr = p.communicate(input=content.encode('ascii'))
		except Exception as e:
			print("Exception attempting to get edited file status: " + e);
		output = output.decode("utf-8")
		try:
			decoded_output = json.loads(output)
		except Exception as e:
			decoded_output = {}
			print("Exception json decoding: " + str(e) + ".  Was attempting to decode '" + output + "'")
		#  Process the results of running flow status on the current file, and determine which regions to highlight
		#  and what error messages to show.
		messages_groups = []
		highlightedRegions[self.cmd.view.file_name()] = []
		if('errors' in decoded_output and decoded_output['errors']):
			for error in decoded_output['errors']:
				if(error['message']):
					if len(error['message']):
						messages_groups.append(error['message']);
				
		underlined_regions = []
		for m in messages_groups:
			new_region = sublime.Region(
				self.cmd.view.text_point(m[0]['line'] -1, m[0]['start'] -1),
				self.cmd.view.text_point(m[0]['endline'] -1, m[0]['end'])
			)
			underlined_regions.append(new_region)
			display_messages = []
			for mes in m:
				display_messages.append(mes['descr'])
			highlightedRegions[self.cmd.view.file_name()].append({'region': new_region, 'messages': display_messages })
		self.cmd.view.add_regions("error", underlined_regions, "keyword", "dot",
			sublime.DRAW_EMPTY |
			sublime.DRAW_NO_FILL |
			sublime.DRAW_NO_OUTLINE |
			sublime.DRAW_SQUIGGLY_UNDERLINE 
		)

class CheckFlowStatusOnView(sublime_plugin.TextCommand):
	#  Start the thread to get flow status on a single file
	def run(self, edit):
		th = CurrentFileFlowStatusThread(self, edit)
		th.start()

class Listener(sublime_plugin.EventListener):
	#  Handles user events that come from Sublime
	def nothing(self,view):
		pass
	def on_activated(self, view):
		if not view.file_name() is None:
			view.run_command("check_flow_status_on_view")
	def on_modified(self, view):
		if not view.file_name() is None:
			view.run_command("check_flow_status_on_view")
	def on_new(self, view):
		if not view.file_name() is None:
			view.run_command("check_flow_status_on_view")
	def on_clone(self, view):
		if not view.file_name() is None:
			view.run_command("check_flow_status_on_view")
	def on_load(self, view):
		if not view.file_name() is None:
			view.run_command("check_flow_status_on_view")
			get_or_create_flow_status_window().run_command('start_flow_status_request', {'current_file_name': view.file_name()})
	def on_post_save(self, view):
		if not view.file_name() is None:
			get_or_create_flow_status_window().run_command('start_flow_status_request', {'current_file_name': view.file_name()})

def create_description_from_flow_error(error):
	#  Create error messages from the decoded json object
	display_strings = []
	for item in error['message']:
		if item['descr']:
			display_strings.append(item['descr'])
	return " ".join(display_strings)

class FinishFlowStatusRequest(sublime_plugin.TextCommand):
	#  Build up the view of error information of all errors
	#  in this project
	def run(self, edit, directory_checked=None, result=''):
		global flowStatusRegions
		global flowRequestThreadCount
		self.view.set_read_only(False)
		self.view.erase(edit, sublime.Region(0, self.view.size()))
		display_messages = []
		decoded_output = None
		try:
			decoded_output = json.loads(result)
		except Exception as e:
			self.view.insert(edit, 0, "Exception json decoding: " + str(e) + ".  Was attempting to decode '" + result + "'")
		if(not decoded_output is None):
			if(decoded_output['passed']):
				self.view.insert(edit, 0, "Flow indicates that everything passed when running flow status in '" + directory_checked + "'. This only considers changes written to disk.\n")
			else:
				all_regions = []
				all_output = "Flow found the following errors when running flow status in '" + directory_checked + "'. This only considers changes written to disk.  Double-click on an error to navigate to it.\n"
				size_before = len(all_output);
				#   Decode Facebook flow's error information:
				if(decoded_output['errors']):
					for error in decoded_output['errors']:
						all_output += "Line " + str(error['message'][0]['line']) + " " + str(error['message'][0]['path'])
						#  Only underline the line number and file to imply a link
						new_region = sublime.Region(size_before, len(all_output))
						all_output += " " + create_description_from_flow_error(error) + "\n"
						size_before = len(all_output) #  New size for next time
						flowStatusRegions.append({'path': error['message'][0]['path'], 'line': error['message'][0]['line'], 'region': new_region})
						all_regions.append(new_region)

				self.view.insert(edit, 0, all_output)
				#  These are the clickable regions in the list of errors that will take us to
				#  the location in the code where the error is.
				self.view.add_regions("underlined_flow_status", all_regions, "keyword", "cross",
					sublime.DRAW_EMPTY |
					sublime.DRAW_NO_FILL |
					sublime.DRAW_NO_OUTLINE |
					sublime.DRAW_SOLID_UNDERLINE
				)
		self.view.set_read_only(True)
		flowRequestThreadCount -= 1

class StartFlowStatusRequest(sublime_plugin.TextCommand):
	#  Used when running 'flow status' on your entire project
	def run(self, edit, current_file_name=None):
		global flowRequestThreadCount
		self.view.set_read_only(False)
		self.view.insert(edit, 0, "Initiated communication with flow server at " + str(datetime.datetime.now()) + "\n")
		self.view.set_read_only(True)
		flowRequestThreadCount += 1
		if flowRequestThreadCount == 1:
			directory = str(os.path.dirname(current_file_name)) if not current_file_name is None else "None"
			statusAnimation = StatusBarProcessingAnimationThread(directory)
			statusAnimation.start()
		th = ProjectFlowStatusThread(self, edit, current_file_name)
		th.start()


class ProcessDoubleClick(sublime_plugin.TextCommand):
	def on_popup_menu_click(self, edit):
		#  This is where you could implement a specific handler that would navigate
		#  to your function/variable declaration or other navigation information
		#  relevant to your error's menu item.
		pass
	def run(self, edit, event):
		#  Sublime doesn't have an 'onclick' event for clicking on text, but you
		#  can remember the locations of the regions that you've underlined, and
		#  then iterate through all of them and check if your click was on that
		#  region.
		global highlightedRegions
		global flowStatusRegions
		pt = self.view.window_to_text((event["x"], event["y"]))
		if self.view.name() == sublime.load_settings('HappyCatSublimeFlow.sublime-settings').get("HappyCatSublimeFlow.FLOW_STATUS_VIEW_NAME"):
			#  Double click to navigate to error message in 'Flow Status' window.
			for r in flowStatusRegions:
				if r['region'].a <= pt and r['region'].b >= pt:
					new_view = sublime.active_window().open_file(r['path'])
					new_pt = new_view.text_point(r['line']-1, 0)
					new_view.sel().clear()
					new_view.sel().add(sublime.Region(new_pt,new_pt))
					new_view.show_at_center(new_pt)
					break
				else:
					pass
		else:
			#  Double click to show error message details in code editor window
			if not self.view.file_name() is None:
				for region in highlightedRegions[self.view.file_name()]:
					if region['region'].a <= pt and region['region'].b >= pt:
						self.view.show_popup_menu(region['messages'], self.on_popup_menu_click)
					else:
						pass
	def want_event(self):
		#  This is what causes the third 'event' parameter to be passed to other methods in this class.
		#  Source:  sublime official API documentation.
		return True
