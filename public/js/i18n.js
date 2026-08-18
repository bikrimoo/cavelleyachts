/* CavelleYachts — i18n Language Switching
   Handles EN ↔ AR language detection, toggle, and persistence */

(function(){
  "use strict";

  var CAV = window.CAV || {};
  window.CAV = CAV;

  /* Detect current language from URL path */
  CAV.getLang = function(){
    var path = window.location.pathname;
    // Arabic pages live under /ar/
    if (path === '/ar/' || path.indexOf('/ar/') === 0) return 'ar';
    return 'en';
  };

  /* Get the equivalent URL in the other language */
  CAV.getAltURL = function(){
    var path = window.location.pathname;
    var query = window.location.search;
    var hash = window.location.hash;

    if (CAV.getLang() === 'ar'){
      // Currently Arabic → switch to English (strip /ar prefix)
      var enPath = path.replace(/^\/ar/, '');
      if (enPath === '' || enPath === '/') enPath = '/';
      return enPath + query + hash;
    } else {
      // Currently English → switch to Arabic (add /ar prefix)
      var arPath;
      if (path === '/' || path === '/index.html'){
        arPath = '/ar/';
      } else {
        arPath = '/ar' + path;
      }
      return arPath + query + hash;
    }
  };

  /* Store language preference */
  CAV.setPref = function(lang){
    try { localStorage.setItem('cav-lang', lang); } catch(e) {}
  };

  CAV.getPref = function(){
    try { return localStorage.getItem('cav-lang'); } catch(e) { return null; }
  };

  /* Set up the language toggle link in the header */
  function setupToggle(){
    var toggles = document.querySelectorAll('[data-lang-toggle]');
    if (!toggles.length) return;

    var altURL = CAV.getAltURL();
    var currentLang = CAV.getLang();

    toggles.forEach(function(toggle){
      toggle.setAttribute('href', altURL);
      toggle.addEventListener('click', function(){
        CAV.setPref(currentLang === 'ar' ? 'en' : 'ar');
      });
    });
  }

  /* On Arabic pages, ensure RTL is properly set */
  function ensureRTL(){
    if (CAV.getLang() === 'ar'){
      document.documentElement.setAttribute('dir', 'rtl');
      document.documentElement.setAttribute('lang', 'ar');
    }
  }

  /* Init */
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){
      ensureRTL();
      setupToggle();
    });
  } else {
    ensureRTL();
    setupToggle();
  }
})();
