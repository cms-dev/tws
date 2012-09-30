/* Translation Web Server
 * Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

function add_notification (type, text) {
    var alert = $('<div class="alert alert-' + type + ' alert-block notification">' +
                  '<a class="close" data-dismiss="alert" href="#">×</a>' +
                  '<h4 class="alert-heading">' + text + '</h4>' +
                  '</div>');

    $("#notifications").prepend(alert);
};

function create_event_source () {
    if (window.es) {
        delete window.es;
    }

    window.es = new EventSource("/events");

    es.addEventListener("open", es_open_handler, false);
    es.addEventListener("error", es_error_handler, false);
    es.addEventListener("reload", es_reload_handler, false);

    es.addEventListener("create", function (event) {
        console.log("create " + event.data);
        var tokens = event.data.split(" ");
        CreateTranslation(tokens[0], tokens[1], tokens[2]);
        if (tokens[0] == current_team) {
            CreateOurTranslation(tokens[1], tokens[2]);
        }
    }, false);
    es.addEventListener("update", function (event) {
        console.log("update " + event.data);
        var tokens = event.data.split(" ");
        UpdateTranslation(tokens[0], tokens[1], tokens[2]);
        if (tokens[0] == current_team) {
            UpdateOurTranslation(tokens[1], tokens[2]);
        }
    }, false);
    es.addEventListener("delete", function (event) {
        console.log("delete " + event.data);
        var tokens = event.data.split(" ");
        DeleteTranslation(tokens[0], tokens[1], tokens[2]);
        if (tokens[0] == current_team) {
            DeleteOurTranslation(tokens[1], tokens[2]);
        }
    }, false);

    es.addEventListener("select", function (event) {
        selections.push(event.data);
        var tokens = event.data.split(" ");
        $("#tab_" + tokens[2] + " .all_translations tbody tr[data-lang=" + tokens[1] + "][data-team=" + tokens[0] + "] td.sel input[type=checkbox]").prop("checked", true);
    }, false);
    es.addEventListener("unselect", function (event) {
        selections.splice(selections.indexOf(event.data), 1);
        var tokens = event.data.split(" ");
        $("#tab_" + tokens[2] + " .all_translations tbody tr[data-lang=" + tokens[1] + "][data-team=" + tokens[0] + "] td.sel input[type=checkbox]").prop("checked", false);
    }, false);
};

function update_network_status (state) {
    $("#notifications .notification.connection").remove();
    if (state == 0) { // self.es.CONNECTING
        $("#ConnectionStatus_box").attr("data-status", "reconnecting");
        $("#ConnectionStatus_text").text("You are disconnected from the server but your browser is trying to connect.");
    } else if (state == 1) { // self.es.OPEN
        $("#ConnectionStatus_box").attr("data-status", "connected");
        $("#notifications").prepend('<div class="alert alert-success alert-block notification connection">' +
                                    '<a class="close" data-dismiss="alert" href="#">×</a>' +
                                    'You are connected to the server and are receiving live updates.' +
                                    '</div>');
    } else if (state == 2) { // self.es.CLOSED
        $("#ConnectionStatus_box").attr("data-status", "disconnected");
        $("#ConnectionStatus_text").html("You are disconnected from the server but you can <a onclick=\"DataStore.create_event_source();\">try to connect</a>.");
    } else if (state == 3) { // "reload" event received
        $("#ConnectionStatus_box").attr("data-status", "outdated");
        $("#ConnectionStatus_text").html("Your local data cannot be updated. Please <a onclick=\"window.location.reload();\">reload the page</a>.");
    }
};

function es_open_handler () {
    if (es.readyState == es.OPEN) {
        console.info("EventSource connected");
        update_network_status(es.readyState);
    } else {
        console.error("EventSource shouldn't be in state " + es.readyState + " during a 'open' event!");
    }
};

function es_error_handler () {
    if (es.readyState == es.CONNECTING) {
        console.info("EventSource reconnecting");
        update_network_status(es.readyState);
    } else if (es.readyState == es.CLOSED) {
        console.info("EventSource disconnected");
        update_network_status(es.readyState);
    } else {
        console.error("EventSource shouldn't be in state " + es.readyState + " during a 'error' event!");
    }
};

function es_reload_handler () {
    if (es.readyState == es.OPEN) {
        console.info("Received a 'reload' event");
        es.close();
        update_network_status(3);
    } else {
        console.error("EventSource shouldn't be in state " + es.readyState + " during a 'reload' event!");
    }
};


selections = new Array();


function init () {
    $('ul.nav li a[data-toggle="tab"]').on('shown', function (evt) {
        var str = $(evt.target).attr("href");
        current_task = str.substr(str.indexOf("_") + 1);
        window.location.hash = current_task;
    });

    if (window.location.hash.substring(1) in task_names) {
        current_task = window.location.hash.substring(1);
        $(".navbar ul.nav [data-task=" + current_task + "]").tab("show");
    }

    $('.navbar a.btn-mini').popover({
        'html': true,
        'placement': 'bottom',
        'title': team_names[current_team],
        'content': '<img src="/flags/' + current_team + '"/>'});


    create_event_source();
    update_network_status(0);


    $(".create_translation").on("click", ".create", function (evt) {
        evt.preventDefault();

        var form = $(this).parents("form");

        var team = current_team;
        var lang = $("[name=lang]", form).val();
        var task = form.parents(".tab_panel").data("task");
        var file = $("[type=file]", form)[0].files[0];

        var others = new Array();
        $("#tab_" + task + " .all_translations tbody tr[data-lang=" + lang + "]").each(function () {
            others.push(team_names[$(this).data("team")]);
        });
        if (others.length > 0) {
            others.sort();
            var msg = "";
            for (var i = 0; i < others.length; i += 1) {
                msg += others[i];
                if (i == others.length - 2) {
                    msg += " and ";
                } else if (i < others.length - 2) {
                    msg += ", ";
                }
            }
            var msg = "\
This task has alredy been translated into " + lang_names[lang] + " by " + msg + ". \
Please avoid uploading again the same PDF file. Instead, you can select their translation \
using the checkboxes in the table to have it highlighted for your contestants, too.\n\
Are you sure you want to upload a new translation?";
            if (!window.confirm(msg)) {
                return;
            }
        }

        if (!file) {
            add_notification("danger", "No file selected");
        } else {
            HTTPRequest("POST", "/translations/" + team + "/" + lang + "/" + task, file, function () {
                add_notification("success", "Upload successful");
            });
        }

        return false;
    });

    $(".update_translations").on("click", ".update", function (evt) {
        evt.preventDefault();

        var form = $(this).parents("form");

        var team = current_team;
        var lang = $("[name=lang]", form).val();
        var task = form.parents(".tab_panel").data("task");
        var file = $("[type=file]", form)[0].files[0];

        if (!file) {
            add_notification("danger", "No file selected");
        } else {
            HTTPRequest("PUT", "/translations/" + team + "/" + lang + "/" + task, file, function () {
                add_notification("success", "Upload successful");
            });
        }

        return false;
    });

    $(".update_translations").on("click", ".delete", function (evt) {
        evt.preventDefault();

        var form = $(this).parents("form");

        var team = current_team;
        var lang = $("[name=lang]", form).val();
        var task = form.parents(".tab_panel").data("task");

        HTTPRequest("DELETE", "/translations/" + team + "/" + lang + "/" + task, null, function () {
            add_notification("success", "Deletion successful");
        });

        return false;
    });


    $(".all_translations").on("change", "tbody tr td.sel input[type=checkbox]", function (evt) {
        var row = $(this).parents("tr");

        var team = row.data("team");
        var lang = row.data("lang");
        var task = row.parents(".tab_panel").data("task");

        if (this.checked) {
            HTTPRequest("PUT", "/selections/" + team + "/" + lang + "/" + task, null, function () {
                add_notification("success", "Action successful");
            });
        } else {
            HTTPRequest("DELETE", "/selections/" + team + "/" + lang + "/" + task, null, function () {
                add_notification("success", "Action successful");
            });
        }
    });
}


function HTTPRequest (method, url, data, callback) {
    var self = this;
    self.callback = callback;
    self.xhr = new XMLHttpRequest();

    self.xhr.upload.addEventListener("loadstart", function (evt) {
        console.log("upload loadstart");
    }, false);

    self.xhr.upload.addEventListener("progress", function (evt) {
        console.log("upload progress");
        if (evt.lengthComputable)
            console.log(evt.loaded + " / " + evt.total);
    }, false);

    self.xhr.upload.addEventListener("abort", function (evt) {
        console.log("upload abort");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.upload.addEventListener("error", function (evt) {
        console.log("upload error");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.upload.addEventListener("load", function (evt) {
        console.log("upload load");
    }, false);

    self.xhr.upload.addEventListener("timeout", function (evt) {
        console.log("upload timeout");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.upload.addEventListener("loadend", function (evt) {
        console.log("upload loadend");
    }, false);

    self.xhr.addEventListener("loadstart", function (evt) {
        console.log("loadstart");
    }, false);

    self.xhr.addEventListener("progress", function (evt) {
        console.log("progress");
        if (evt.lengthComputable)
            console.log(evt.loaded + " / " + evt.total);
    }, false);

    self.xhr.addEventListener("abort", function (evt) {
        console.log("abort");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.addEventListener("error", function (evt) {
        console.log("error");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.addEventListener("load", function (evt) {
        console.log("load");
        if (evt.target.status == 200) {
            self.callback.call();
        } else {
            add_notification("danger", "An error occurred");
        }
    }, false);

    self.xhr.addEventListener("timeout", function (evt) {
        console.log("timeout");
        add_notification("danger", "An error occurred");
    }, false);

    self.xhr.addEventListener("loadend", function (evt) {
        console.log("loadend");
    }, false);

    self.xhr.open(method, url);
    self.xhr.send(data);
}


function CreateOurTranslation (lang, task) {
    // Add a box
    var box = $(' \
<div class="translation" data-lang="' + lang + '"> \
    <form autocomplete="off"> \
        <h3> \
            ' + lang_names[lang] + ' \
        </h3> \
        <input type="hidden" name="lang" value="' + lang + '"/> \
        <input type="file" name="statement"/> \
        <button class="btn btn-primary update">Upload</button> \
        <button class="btn btn-danger delete">Delete</button> \
        </div> \
    </form> \
</div>');

    var found = false;
    $("#tab_" + task + " .update_translations div.translation").each(function () {
        if (!found && $(this).data("lang") >= lang) {
            found = true;
            box.insertBefore(this);
        }
    });

    if (!found) {
        $("#tab_" + task + " .update_translations").append(box);
    }

    $("#tab_" + task + " .create_translation form")[0].reset();

    $("#tab_" + task + " .create_translation select option[value=" + lang + "]").eq(0).attr("disabled", "");
    $("#tab_" + task + " .create_translation select option:not([disabled])")[0].selected = true;
}

function UpdateOurTranslation (lang, task) {
    $("#tab_" + task + " .update_translation div.translation[data-lang=" + lang + "] form")[0].reset();
}

function DeleteOurTranslation (lang, task) {
    // Remove a box
    $('#tab_' + task + ' .update_translations div.translation[data-lang="' + lang + '"]').remove();

    $("#tab_" + task + " .create_translation select option[value=" + lang + "]").eq(0).removeAttr("disabled");
    // $("#tab_" + task + " .create_translation select option:not([disabled])")[0].selected = true;
}


function CreateTranslation (team, lang, task) {
    // Add a row in the table
    var row = $(' \
<tr data-lang="' + lang + '" data-team="' + team + '"> \
    <td class="sel"> \
        <input type="checkbox"/> \
    </td> \
    <td class="lang"> \
        ' + lang_names[lang] + ' \
    </td> \
    <td class="team"> \
        ' + team_names[team] + ' \
    </td> \
    <td class="download"> \
        <a class="btn btn-success" href="/translations/' + team + '/' + lang + '/' + task + '">Download</a> \
    </td> \
</tr>');

    var found = false;
    $("#tab_" + task + " .all_translations tbody tr").each(function () {
        if (!found && $(this).data("lang") >= lang || ($(this).data("lang") == lang && $(this).data("team") >= team)) {
            found = true;
            row.insertBefore(this);
        }
    });

    if (!found) {
        $("#tab_" + task + " .all_translations tbody").append(row);
    }

    if (selections.indexOf(team + " " + lang + " " + task) != -1) {
        $("#tab_" + task + " .all_translations tbody tr[data-lang=" + lang + "][data-team=" + team + "] td.sel input[type=checkbox]").prop("checked", true);
    }

    if (team == current_team || team == "HSC") {
        $("#tab_" + task + " .all_translations tbody tr[data-lang=" + lang + "][data-team=" + team + "] td.sel input[type=checkbox]").prop("checked", true);
        $("#tab_" + task + " .all_translations tbody tr[data-lang=" + lang + "][data-team=" + team + "] td.sel input[type=checkbox]").prop("disabled", true);
    }
}

function UpdateTranslation (team, lang, task) {

}

function DeleteTranslation (team, lang, task) {
    // Remove a row in the table
    $('#tab_' + task + ' .all_translations tbody tr[data-lang="' + lang + '"][data-team="' + team + '"]').remove();
}
