import { createApp } from "vue";
import App from "./App.vue";
import axios from "axios";

import "./assets/styles.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js";

axios.defaults.baseURL = "http://localhost:5001";

// set auth header if token present
const token = localStorage.getItem("token");
if (token) {
  axios.defaults.headers.common["Authorization"] = "Bearer " + token;
}

// make axios globally accessible for quick console testing
window.axios = axios;

const app = createApp(App);
app.config.globalProperties.$axios = axios;

// update header on user-changed events
window.addEventListener("user-changed", () => {
  const t = localStorage.getItem("token");
  if (t) axios.defaults.headers.common["Authorization"] = "Bearer " + t;
  else delete axios.defaults.headers.common["Authorization"];
});

app.mount("#app");
