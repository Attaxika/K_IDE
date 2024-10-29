# -*- coding: utf-8 -*-
#!/usr/bin/python2
#Version 0.2.6
#Made by: Brandon Kimball


#Imports
import os,gi,sys,urllib,subprocess,json,threading,gc
from subprocess import Popen,PIPE
#GI
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import GLib, Gtk, Gdk, GtkSource, Gio, Pango

#Application
class KIDE(Gtk.Application):
    #Globals
    auto_detect = False
    process = Popen(["echo", "", ""])
    prefs_content = ""
    word_wrap = True
    syntax = "python"
    compiler = "python"
    working_dir = "working-dir"
    save_buffer = ""
    prefs_default = {
        "word_wrap" : "True",
        "lang" : "python",
        "compiler" : "python",
        "scheme" : "classic",
        "valid_schemes" : "classic, cobalt, kate, oblivion, solarized-dark, solarized,light, tango",
        "auto_detect" : "False"
    }
    current_file = ""
    previous_file = ""
    auto_save = False
    scheme = "classic"

	#Constructor
    def __init__(self):
        super(KIDE, self).__init__(application_id="com.ballin.kide")
        GLib.set_application_name("KIDE")
        self.connect("activate", self.on_activate) 
	#Gtk construction
    def on_activate(self, app):
        #Main window
        window = Gtk.ApplicationWindow(application=self, title="KIDE", resizable=True)
        window.set_size_request(750,500)
        grid = Gtk.Grid()
        window.add(grid)

        #Close interrupt
        window.connect("delete-event", self.intercept_delete)

        #GTK Objects
        action_bar = Gtk.ActionBar()
        file_menu = Gtk.Menu()

        #File menu dropdown
        new_item = Gtk.MenuItem(label="New")
        open_item = Gtk.MenuItem(label="Open")
        self.save_item = Gtk.MenuItem(label="Save")

        file_menu.append(new_item)
        file_menu.append(open_item)
        file_menu.append(self.save_item)
        file_menu.show_all()

        #Action Bar
        file_button = Gtk.MenuButton(label="File")
        file_button.set_popup(file_menu)
        run_button = Gtk.Button(label="Run")
        self.prefs_button = Gtk.Button(label="Prefs")
        refresh_button = Gtk.Button(label="Refresh")
        auto_save_button = Gtk.CheckButton(label="Auto-Save")
        find_label = Gtk.Label("Find:")
        find_entry = Gtk.Entry()
        action_bar.add(run_button)
        action_bar.add(file_button)
        action_bar.add(self.prefs_button)
        action_bar.add(refresh_button)
        action_bar.add(auto_save_button)
        action_bar.add(find_label)
        action_bar.add(find_entry)
        grid.attach(action_bar,0,0,1,1)

        #Coding text
        coding_window = Gtk.ScrolledWindow()
        self.coding_buffer = GtkSource.Buffer()
        self.coding_pane = GtkSource.View.new_with_buffer(self.coding_buffer)
        self.coding_buffer.can_redo()
        self.coding_buffer.can_undo()
        self.coding_pane.set_hexpand(True)
        self.coding_pane.set_vexpand(True)
        self.coding_pane.set_indent_on_tab(True)
        self.coding_pane.set_auto_indent(True)
        coding_window.add(self.coding_pane)

        #File browser
        self.file_store = Gtk.ListStore(str)
        self.file_view = Gtk.TreeView(model=self.file_store)
        working_window = Gtk.Paned()
        working_window.add(self.file_view)
        self.file_view.set_size_request(100,50)
        self.file_renderer = Gtk.CellRendererText()
        self.file_column = Gtk.TreeViewColumn("working-dir", self.file_renderer, text=0)
        self.file_view.append_column(self.file_column)
        self.populate_file_list(self.file_view)
        tree_selection = self.file_view.get_selection()
        working_window.pack1(self.file_view, True, True)
        self.file_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        working_window.pack2(coding_window, True, True)
        working_window.set_position(200)
        grid.attach(working_window,0,1,1,1)
        grid.add(working_window)
        working_window.add(coding_window)

        #Connections
        open_item.connect("activate", self.open_file)
        self.save_item.connect("activate", self.save_changes, False, False)
        run_button.connect("clicked", self.run_thread)
        self.prefs_button.connect("clicked", self.show_prefs)
        refresh_button.connect("clicked", self.populate_file_list)
        auto_save_button.connect("toggled", self.auto_save_func)
        tree_selection.connect("changed", self.file_viewer_open)
        new_item.connect("activate", self.gen_new, tree_selection)
        self.coding_buffer.connect("changed", self.auto_saving)
        find_entry.connect("activate", self.search)
        window.connect("key-release-event", self.key_handler)

        self.add_monitor()

        #Final
        window.show_all()
        window.present()
	
    def auto_dir_update(self, monitor, f1, f2, event_type):
        if event_type in [Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.RENAMED]:
            self.populate_file_list(self.save_item)
	
    def add_monitor(self):
        gdir = Gio.File.new_for_path(self.working_dir)
        self.monitor = gdir.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self.auto_dir_update)

    def reset_buffer_and_view(self, buffer_cont):
        pointer_position = ""
        new_iter = ""
        try:
            pointer_position = self.coding_buffer.get_iter_at_mark(self.coding_buffer.get_insert()).get_offset()
            new_iter = self.coding_buffer.get_iter_at_offset(pointer_position)
        except Exception as e:
            pass

        temp_buffer = GtkSource.Buffer()
        self.coding_pane.set_buffer(temp_buffer)
        self.coding_buffer = None
        self.coding_buffer = GtkSource.Buffer()
        GLib.idle_add(self.coding_pane.set_buffer, self.coding_buffer)
        temp_buffer = None
        self.coding_buffer.begin_not_undoable_action()
        self.coding_buffer.set_text("")
        self.coding_buffer.set_text(buffer_cont)
        self.coding_buffer.end_not_undoable_action()

        try:
            new_iter = self.coding_buffer.get_iter_at_offset(pointer_position)
            self.coding_buffer.place_cursor(new_iter)
            cursor_pos = self.coding_buffer.get_insert()
            GLib.idle_add(self.coding_pane.scroll_to_mark, cursor_pos, 0.1, True, 0.0, 0.5)
        except Exception as e:
            print(e)
            pass

    def intercept_delete(self, widget, event):
        if self.save_buffer != self.get_coding_content()[:]:
            self.save_changes(widget,False,False)
        else:
            Gtk.Widget.get_toplevel(widget).destroy()
            self.process.terminate()
        for window in Gtk.Window.list_toplevels():
            window.destroy()
        return True

    def gen_prefs(self):
        if not os.path.isfile("prefs.json"):
            with open("prefs.json", "wb") as file:
                file.write(json.dumps(self.prefs_default, sort_keys=True, indent=4))
        with open("prefs.json", "r") as file:
            prefs_content = json.load(file)
        self.word_wrap = prefs_content.get("word_wrap")
        self.syntax = prefs_content.get("lang")
        self.compiler = prefs_content.get("compiler")
        self.scheme = prefs_content.get("scheme")
        self.coding_pane.set_show_line_numbers(True)
        lang_manager = GtkSource.LanguageManager()
        lang = lang_manager.get_language("{}".format(self.syntax))
        self.coding_buffer.set_language(lang)
        self.coding_buffer.set_style_scheme(GtkSource.StyleSchemeManager().get_default().get_default().get_scheme("{}".format(self.scheme)))
        if self.word_wrap == "True":
            self.coding_pane.set_wrap_mode(Gtk.WrapMode.WORD)
        else:
            self.coding_pane.set_wrap_mode(Gtk.WrapMode.NONE)
        if self.auto_detect == "True":
            if ".py" in self.current_file:
                self.syntax = "python"
                self.compiler = "python"
            elif ".html" in self.current_file:
                self.syntax = "html"
                self.compiler = "gio open"
            elif ".css" in self.current_file:
                self.syntax = "css"
                self.compiler = "echo 'Open your associated HTML file'"
            elif ".cs" in self.current_file:
                self.syntax = "csharp"
                self.compiler = "gcc"
            elif ".cpp" in self.current_file:
                self.syntax = "cpp"
                self.compiler = "gcc"
            elif ".java" in self.current_file:
                self.syntax = "java"
                self.compiler = "java"
            elif ".sh" in self.current_file:
                self.syntax = "bash"
                self.compiler = "bash"
            elif ".rs" in self.current_file:
                self.syntax = "rust"
                self.compiler = "echo 'No rust compiler built in :( Sorry'"
            elif ".json" in self.current_file:
                self.syntax = "json"
                self.compiler = "echo 'JSON is not runnable'"
            else:
                self.syntax = "plaintext"
                self.compiler = "echo 'No associated lang found'"

    def get_coding_content(self):
        gc.collect()
        start_iter, end_iter = self.coding_buffer.get_bounds()
        cont = self.coding_buffer.get_text(start_iter, end_iter, False)
        self.gen_prefs()
        return cont

    def populate_file_list(self, widget):
        self.gen_prefs()
        self.file_store.clear()
        if not os.path.isdir(os.getcwd()+"/{}".format(self.working_dir)):
            subprocess.call(["mkdir", "{}".format(self.working_dir)])
        file_store_path = os.getcwd()+"/{}".format(self.working_dir)
        for root, dirs, files in os.walk(self.working_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                if os.path.isfile(filepath):
                    new_file = filepath[filepath.find(str("/{}/".format(self.working_dir))) + 1:]
                    self.file_store.append([new_file])

    def update_save_buffer(self, update_previous):
        if update_previous:
            self.previous_file = self.current_file[:]
            if self.previous_file != "":
                try:
                    with open(self.previous_file, "r") as file:
                        self.save_buffer = file.read()
                except Exception as e:
                    print(e)
        else:
            self.save_buffer = self.get_coding_content()[:]

    def file_viewer_open(self, selection):
        self.reset_buffer_and_view(self.get_coding_content()[:])
        self.update_save_buffer(True)
        model, tree_iter = selection.get_selected()
        coding_text = self.get_coding_content()[:]
        if not self.auto_save:
            coding_text = self.get_coding_content()[:]
            if not self.save_buffer == coding_text:
                self.save_changes(self.save_item, True, False)
        else:
            try:
                with open(self.previous_file, "wb") as file:
                    self.coding_buffer.begin_not_undoable_action()  
                    file.write(coding_text)
                    self.coding_buffer.end_not_undoable_action()
                self.current_file = model[tree_iter][0]
            except Exception as e:
                print(e)
        self.previous_file = self.current_file[:]
        
        try:
            filename = model[tree_iter][0]
            with open(filename, "r") as file:
                content = file.read()
                self.coding_buffer.set_text(content)
                coding_text = content[:]
                self.update_save_buffer(False)
            self.current_file = filename
        except Exception as e:
            print(e)

    def gen_new(self, widget, selection):
        self.update_save_buffer(True)
        self.coding_buffer.begin_not_undoable_action() 
        content = self.get_coding_content()[:]
        self.coding_buffer.end_not_undoable_action() 
        if not self.save_buffer == content[:]:
            self.save_changes(widget, True, False)
        self.save_buffer = ""
        self.coding_buffer.set_text("")
        self.current_file = ""
        selection.unselect_all()

    def open_file(self, widget):
        if not self.auto_save:
            if not self.save_buffer == self.get_coding_content()[:]:
                self.save_changes(widget, True, False)
        else:
            try:
                with open(self.previous_file, "wb") as file:
                    self.coding_buffer.begin_not_undoable_action() 
                    file.write(self.get_coding_content()[:])
                    self.coding_buffer.end_not_undoable_action() 
            except Exception as e:
                print(e)

        dialog = Gtk.FileChooserDialog(title="Select File", parent=Gtk.Widget.get_toplevel(widget), action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_select_multiple(False)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            model, tree_iter = self.file_view.get_selection().get_selected()
            try:
                test = model(tree_iter[0])
                self.file_view.get_selection().unselect_all()
                content = self.get_coding_content()[:]
                self.update_save_buffer(True)
            except TypeError as e:
                self.current_file = str(os.path.dirname(urllib.unquote(dialog.get_uri())[7:]))+"/"+str(os.path.basename(urllib.unquote(dialog.get_uri())[7:]))
                with open(self.current_file, "r") as file:
                    self.save_buffer = file.read()
            self.open_file = urllib.unquote(dialog.get_uri())
            with open(self.open_file[7:]) as file:
                self.coding_buffer.set_text(file.read())
                self.save_buffer = file.read()
                self.current_file = str(os.path.dirname(self.open_file[7:]))+"/"+str(os.path.basename(self.open_file[7:]))
        dialog.destroy()

    def save_changes(self, widget, boolean, delete):
        content = self.get_coding_content()[:]
        if os.path.isfile(self.current_file):
            if boolean:
                dialog = Gtk.MessageDialog(Gtk.Widget.get_toplevel(widget), Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, "Save?")
                response = dialog.run()
                if response == Gtk.ResponseType.YES:
                    self.update_save_buffer(False)
                    with open(self.current_file, "wb") as file:
                        file.write(content)
                dialog.destroy()
            else:
                self.update_save_buffer(False)
                with open(self.current_file, "wb") as file:
                    file.write(content)
        else:
            dialog = Gtk.FileChooserDialog(title="Save as…", parent=Gtk.Widget.get_toplevel(widget), action=Gtk.FileChooserAction.SAVE)
            dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                filename = dialog.get_filename()
                self.update_save_buffer(True)
                with open(filename, "wb") as file:
                    self.current_file = filename
                    file.write(content)
                model = self.file_view.get_model()
                iter = model.get_iter_first()
                while iter:
                    if model[iter][0] == filename:
                        path = model.get_path(iter)
                        self.file_view.get_selection().select_iter(model.get_iter(Gtk.TreePath([self.file_view.get_row_by_filename(filename)])))
                    iter = model.iter_next(iter)
            dialog.destroy()
        if delete:
            Gtk.Widget.get_toplevel(widget).destroy()
            self.process.terminate()

    def change_prefs(self, widget, word_wrap_widget, compiler_widget, lang_widget, scheme_widget, auto_detect_widget):
        prefs_update = {
            "word_wrap" : "{}".format(str(word_wrap_widget.get_active())),
            "lang" : lang_widget.get_text(),
            "compiler" : compiler_widget.get_text(),
            "scheme" : scheme_widget.get_text(),
            "valid_schemes" : "classic, cobalt, kate, oblivion, solarized-dark, solarized-light, tango",
            "auto_detect" : "{}".format(str(auto_detect_widget.get_active()))
        }
        with open("prefs.json", "wb") as file:
            file.write(json.dumps(prefs_update, sort_keys=True, indent=4))
        self.reset_buffer_and_view(self.get_coding_content()[:])
        self.populate_file_list(widget)

    def show_prefs(self, widget):
        self.gen_prefs()
        self.prefs_button.set_sensitive(False)
        prefs_window = Gtk.ApplicationWindow(application=self, title="Preferences", resizable=False)
        prefs_window.set_size_request(250,250)
        prefs_grid = Gtk.Grid()
        prefs_window.add(prefs_grid)

        #Prefs items
        word_wrap_button = Gtk.CheckButton(label="Word wrap")
        auto_detect_button = Gtk.CheckButton(label="Auto detect lang.")
        compiler_pane = Gtk.Entry()
        compiler_label = Gtk.Label(label="Compiler")
        lang_label = Gtk.Label(label="Lang")
        lang_pane = Gtk.Entry()
        scheme_label = Gtk.Label(label="Scheme")
        scheme_pane = Gtk.Entry()
        spacer_label = Gtk.Label(label="")
        save_prefs_button = Gtk.Button(label="Save prefs")
        
        #Attach items
        prefs_grid.attach(word_wrap_button,0,0,1,1)
        prefs_grid.attach(auto_detect_button,0,1,1,1)
        prefs_grid.attach(compiler_label,0,2,1,1)
        prefs_grid.attach(compiler_pane,1,2,1,1)
        prefs_grid.attach(lang_label,0,3,1,1)
        prefs_grid.attach(lang_pane,1,3,1,1)
        prefs_grid.attach(scheme_label,0,4,1,1)
        prefs_grid.attach(scheme_pane,1,4,1,1)
        prefs_grid.attach(spacer_label,1,5,1,1)
        prefs_grid.attach(save_prefs_button,1,6,1,1)

        with open("prefs.json", "r") as file:
            prefs_content = json.load(file)
        
        if prefs_content.get("word_wrap") == "True":
            word_wrap_button.set_active(True)
        if prefs_content.get("auto_detect") == "True":
            auto_detect_button.set_active(True)
        compiler_pane.set_text(prefs_content.get("compiler"))
        lang_pane.set_text(prefs_content.get("lang"))
        scheme_pane.set_text(prefs_content.get("scheme"))
        
        save_prefs_button.connect("clicked", self.change_prefs, word_wrap_button, compiler_pane, lang_pane, scheme_pane, auto_detect_button)

        def on_delete(widget, event):
            self.prefs_button.set_sensitive(True)
        
        prefs_window.connect("delete-event", on_delete)

        prefs_window.show_all()
        prefs_window.present()

    def auto_save_func(self, widget):
        self.auto_save = not self.auto_save
        if self.auto_save and not os.path.isfile(self.current_file):
            self.save_changes(False, False)

    def auto_saving(self, widget):
        content = self.get_coding_content()[:]
        if os.path.isfile(self.current_file) and self.auto_save:
            self.update_save_buffer(False)
            with open(self.current_file, "wb") as file:
                file.write(content[:])

    def search(self, entry):
        search_text = entry.get_text()
        if hasattr(self, 'last_match_end'):
            start_iter = self.last_match_end
        else:
            start_iter = self.coding_buffer.get_start_iter()

        match = start_iter.forward(search_text, Gtk.TextSearchFlags.TEXT_ONLY, None)
        if match:
            match_start, match_end = match
            self.coding_buffer.select_range(match_start, match_end)
            self.coding_pane.scroll_to_iter(match_start, 0.0, False, 0.0, 0.0)
            self.last_match_end = match_end
        else:
            self.last_match_end = self.coding_buffer.get_start_iter()

    def key_handler(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "s" and (event.state & Gdk.ModifierType.CONTROL_MASK):
            self.save_changes(widget,False,False)
        if keyname == "d" and (event.state & Gdk.ModifierType.CONTROL_MASK):
            start, end = self.coding_buffer.get_bounds()
            cursor_iter = self.coding_buffer.get_iter_at_mark(self.coding_buffer.get_insert())
            start_iter = cursor_iter.copy()
            if not start_iter.starts_line():
                start_iter.set_line_offset(0)
            else:
                start_iter.backward_line()
            end_iter = start_iter.copy()
            end_iter.forward_to_line_end()
            end_iter.forward_char()
            try:
                self.coding_buffer.begin_user_action()
                self.coding_buffer.delete(start_iter, end_iter)
                self.coding_buffer.end_user_action()
            except:
                pass
        return True

    def run_program(self, process):
        try:
            self.process = Popen(["gnome-terminal", "--", "bash", "-c", "{} .run_file; echo '[KIDE DEBUG]: Press ENTER key to exit...';read".format(self.compiler)], stderr=PIPE, stdout=PIPE, universal_newlines=True)
        except Exception as e:
            print(e)
		
    def run_thread(self, widget):
        try:
            with open(".run_file".format(), "wb") as file:
                file.write(self.get_coding_content())
            self.process.terminate()
        except Exception as e:
            print(e)
        process_thread = threading.Thread(target=self.run_program, args=(self.process,))
        process_thread.start()

app = KIDE()
exit_status = app.run(sys.argv)
sys.exit(exit_status)
