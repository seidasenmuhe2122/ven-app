(() => {
  document.querySelectorAll('[data-admin-access-hold]').forEach((target) => {
    let timer = null;

    const cancelHold = () => {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
    };

    target.addEventListener('pointerdown', (event) => {
      if (!event.isPrimary || (event.pointerType === 'mouse' && event.button !== 0)) return;
      cancelHold();
      try {
        target.setPointerCapture(event.pointerId);
      } catch (_) {
        // Pointer capture is unavailable for some synthetic events.
      }
      timer = window.setTimeout(() => {
        timer = null;
        const encodedUrl = target.dataset.adminLoginEncoded;
        if (encodedUrl) window.location.assign(window.atob(encodedUrl));
      }, 8000);
    });

    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach((eventName) => {
      target.addEventListener(eventName, cancelHold);
    });
    target.addEventListener('contextmenu', (event) => event.preventDefault());
  });
})();