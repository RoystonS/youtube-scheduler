const SERVICE_WORKER_PATH = "/service-worker.js";
const MESSAGE_TYPES = Object.freeze({
  NETWORK_ERROR: "network-error",
  SERVER_ERROR: "server-error",
  ONLINE: "network-ok",
  STATUS_REQUEST: "status-request"
});

const BANNER_COPY = Object.freeze({
  [MESSAGE_TYPES.NETWORK_ERROR]: {
    heading: "Connection issue. Showing cached schedule data.",
    showContact: false
  },
  [MESSAGE_TYPES.SERVER_ERROR]: {
    heading: "Server error. Showing cached schedule data.",
    showContact: true
  }
});

const getOfflineBanner = () => document.querySelector(".offline-banner");
const getBannerHeading = () => document.querySelector(".offline-heading");
const getBannerContact = () => document.querySelector(".offline-contact");

const setBannerVisibility = (visible) => {
  const banner = getOfflineBanner();
  if (!banner) {
    return;
  }

  if (visible) {
    banner.classList.add("visible");
  } else {
    banner.classList.remove("visible");
  }
};

const setBannerContent = (type) => {
  const heading = getBannerHeading();
  const contact = getBannerContact();
  const copy = BANNER_COPY[type] ?? BANNER_COPY[MESSAGE_TYPES.NETWORK_ERROR];

  if (heading) {
    heading.textContent = copy.heading;
  }

  if (copy.showContact) {
    contact.classList.add("visible");
  }
};

const showOfflineBanner = (type) => {
  setBannerContent(type);
  setBannerVisibility(true);
};

const hideOfflineBanner = () => {
  setBannerVisibility(false);
};

const registerServiceWorker = async () => {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  try {
    await navigator.serviceWorker.register(SERVICE_WORKER_PATH);
  } catch (error) {
    console.error("Failed to register service worker", error);
  }
};

const handleServiceWorkerMessage = (event) => {
  const { type } = event.data || {};
  if (type === MESSAGE_TYPES.NETWORK_ERROR || type === MESSAGE_TYPES.SERVER_ERROR) {
    showOfflineBanner(type);
  } else if (type === MESSAGE_TYPES.ONLINE) {
    hideOfflineBanner();
  }
};

const requestServiceWorkerStatus = () => {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const sendStatusRequest = (target) => {
    if (target) {
      target.postMessage({ type: MESSAGE_TYPES.STATUS_REQUEST });
    }
  };

  if (navigator.serviceWorker.controller) {
    sendStatusRequest(navigator.serviceWorker.controller);
  } else {
    navigator.serviceWorker.ready.then((registration) => sendStatusRequest(registration.active));
  }
};

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.addEventListener("message", handleServiceWorkerMessage);
}

document.addEventListener("DOMContentLoaded", () => {
  registerServiceWorker();
  requestServiceWorkerStatus();
});
