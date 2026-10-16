document.addEventListener('DOMContentLoaded', function () {
  function initRichTextFields() {
    if (typeof tinymce === 'undefined') {
      return;
    }

    const editors = document.querySelectorAll('textarea.rich-text-editor');
    editors.forEach(function (textarea) {
      if (textarea.dataset.richTextInitialized === 'true') {
        return;
      }

      const config = {
        target: textarea,
        branding: false,
        menubar: false,
        plugins: 'advlist autolink lists link image charmap preview anchor wordcount code color fontfamily fontsize table fullscreen visualblocks searchreplace media autoresize',
        toolbar: 'undo redo | blocks fontfamily fontsize forecolor backcolor | bold italic underline strikethrough | alignleft aligncenter alignright | bullist numlist outdent indent | link image media table | searchreplace preview fullscreen code',
        fontsize_formats: '10px 12px 14px 16px 18px 20px 24px 28px 32px 40px 48px 56px 72px',
        font_size_input_default_unit: 'px',
        color_map: [
          '000000', 'Black',
          'FFFFFF', 'White',
          'D32F2F', 'Red',
          'F57C00', 'Orange',
          'FBC02D', 'Yellow',
          '388E3C', 'Green',
          '1976D2', 'Blue',
          '7B1FA2', 'Purple',
          '616161', 'Gray'
        ],
        toolbar_mode: 'wrap',
        resize: true,
        height: 280,
        setup: function (editor) {
          editor.on('init', function () {
            textarea.dataset.richTextInitialized = 'true';
          });
        },
        init_instance_callback: function () {
          textarea.dataset.richTextInitialized = 'true';
        }
      };

      tinymce.init(config).catch(function () {
        delete textarea.dataset.richTextInitialized;
      });
    });
  }

  initRichTextFields();
  if (window.django && django.jQuery) {
    django.jQuery(document).on('formset:added', function () {
      initRichTextFields();
    });
  }

  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      if (window.tinymce) {
        tinymce.triggerSave();
      }
    });
  });
});
