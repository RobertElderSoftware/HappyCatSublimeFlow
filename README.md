#  What this plugin is about

This plugin is a failed attempt to create a plugin to integrate Facebook flow into sublime text.  The idea was to provide functionality that would make it easy to navigate and find javascript errors from withing sublime.  After spending quite a bit of time researching and prototyping what plugin UI features exist, it was decided that Sublime's plugin API is not currently adequate for implementing this type of plugin in a way that has a high quality user experience.  Reasons are listed in the next section.

#  Difficulty Building UI Features In Sublime

-  Single click for showing detailed error information isn't practical and causes a very negative user experience (you get error info when you click on a line trying to edit it).
-  It is not possible to change the cursor to a hand icon to suggest to the user that you can click on certain text.
-  No detection for hovering on text at all.
-  No ability to implement a 'status window' at the bottom of the screen (similar to MS Visual Studio).  Printing to the console isn't a practical alternative.
-  Simply changing the colour of underlined text has no obvious simple solution.  This is definitely possible (plugin source url here) but, my investigation suggests, that you need to jump through elaborate hoops by defining the underline as a style using hard-coded colour values for each color according to an XML format,  then register this with the settings object.  This must be done for every individual colour underline that you use.

#  TODO

These tasks were not completed since the original goals of the plugin don't seem to be achievable in a reasonable amount of time (or not at all, given the UI mechanisms that Sublime offers).

-  Don't use full verbose method of loading settings (loading settings is async and)
-  When an error popup menu appears (from double-clicking on an error), navigate the user to the relevant section of the code that appears in the menu (such as a function definition).
