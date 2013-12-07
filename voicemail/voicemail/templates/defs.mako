<%def name="flash()">
<div id='flash'>${getattr(c, 'flash') or ""}</div>
</%def>

## flash messages with css class und fade in options
<%def name="flash_messages()">
    % if request.session.peek_flash():
        <% flash = request.session.pop_flash() %>
        % for message in flash:
            <div class="alert alert-${message.split(';')[0]} alert-dismissable">
            <a class="close" data-dismiss='alert'>×</a>
            ${message.split(";")[1]}</div>
        % endfor
    % endif
</%def>
