<%inherit file="/base.mako" />
<%namespace name="defs" file="/defs.mako"/>
<%def name="title()">Add User</%def>
<div id="details">
        %if form:
          ${form|n}
        %endif
    <script type="text/javascript">
        deform.load()
    </script>
</div>
