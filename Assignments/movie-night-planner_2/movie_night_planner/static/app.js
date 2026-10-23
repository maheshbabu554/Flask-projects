/**
 * Movie Night Planner - Client-side Interactive Features
 * Provides trailer modal playback, delete confirmations, and image fallbacks.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Auto-dismiss flash alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach((alert) => {
    setTimeout(() => {
      try {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
      } catch (e) {
        // Fallback if bootstrap instance is unavailable
        alert.remove();
      }
    }, 6000);
  });

  // 2. Trailer Modal Video Handling
  // Ensures video starts when modal opens and stops playback when modal is closed
  const trailerModal = document.getElementById('trailerModal');
  const trailerFrame = document.getElementById('trailerModalIframe');
  const trailerModalTitle = document.getElementById('trailerModalTitle');

  if (trailerModal && trailerFrame) {
    trailerModal.addEventListener('show.bs.modal', (event) => {
      const button = event.relatedTarget;
      if (!button) return;

      const videoEmbedUrl = button.getAttribute('data-trailer-url');
      const movieTitle = button.getAttribute('data-movie-title') || 'Movie Trailer';

      if (trailerModalTitle) {
        trailerModalTitle.textContent = `${movieTitle} - Trailer`;
      }

      // Set iframe source with autoplay=1 when user intentionally opens trailer
      if (videoEmbedUrl) {
        const separator = videoEmbedUrl.includes('?') ? '&' : '?';
        trailerFrame.src = `${videoEmbedUrl}${separator}autoplay=1`;
      }
    });

    trailerModal.addEventListener('hidden.bs.modal', () => {
      // Clear iframe src to stop video audio when modal closes
      trailerFrame.src = '';
    });
  }

  // 3. Fallback for broken movie poster images
  const posterImages = document.querySelectorAll('img.movie-poster-img');
  posterImages.forEach((img) => {
    img.addEventListener('error', function() {
      if (!this.getAttribute('data-fallback-applied')) {
        this.setAttribute('data-fallback-applied', 'true');
        this.src = '/static/images/movie-placeholder.svg';
      }
    });
  });
});
