<template>
  <div class="card mx-auto" style="max-width:420px">
    <div class="card-body">
      <h5 class="card-title">Login</h5>

      <div class="mb-3">
        <label class="form-label">Username</label>
        <input v-model="username" type="text" class="form-control" />
      </div>

      <div class="mb-3">
        <label class="form-label">Password</label>
        <input v-model="password" type="password" class="form-control" />
      </div>

      <div class="d-flex gap-2">
        <button :disabled="loading" class="btn btn-primary" @click="loginUser">
          {{ loading ? 'Logging...' : 'Login' }}
        </button>
        <button class="btn btn-secondary" @click="goRegister">Register</button>
      </div>

      <div v-if="error" class="alert alert-danger mt-3" role="alert">
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "LoginView",
  data() {
    return {
      username: "",
      password: "",
      loading: false,
      error: null
    };
  },
  methods: {
    goRegister() {
      // navigate to register in parent app
      if (this.$root) this.$root.view = "Register";
    },

    async loginUser() {
      this.error = null;
      if (!this.username || !this.password) {
        this.error = "Please enter username and password.";
        return;
      }

      this.loading = true;
      try {
        // prefer this.$axios if set, else fallback to axios import
        const http = this.$axios ? this.$axios : axios;

        // make request (http.baseURL should be set in main.js)
        const resp = await http.post("/auth/login", {
          username: this.username,
          password: this.password
        });

        // check response
        if (!resp || !resp.data || !resp.data.token) {
          throw new Error("Invalid server response");
        }

        const token = resp.data.token;
        const user = resp.data.user;

        // store token/user
        localStorage.setItem("token", token);
        localStorage.setItem("user", JSON.stringify(user));

        // ensure global axios (and this.$axios) send the token
        window.axios = window.axios || axios;
        window.axios.defaults.headers = window.axios.defaults.headers || {};
        window.axios.defaults.headers.common = window.axios.defaults.headers.common || {};
        window.axios.defaults.headers.common["Authorization"] = "Bearer " + token;

        // also ensure this.$axios is updated (if used)
        if (this.$axios && this.$axios.defaults) {
          this.$axios.defaults.headers.common["Authorization"] = "Bearer " + token;
        }


        window.dispatchEvent(new Event("user-changed"));
        if(this.$root)  this.$root.view = "UserDash";

        // set axios defaults (both instances)
        http.defaults.headers = http.defaults.headers || {};
        http.defaults.headers.common = http.defaults.headers.common || {};
        http.defaults.headers.common["Authorization"] = "Bearer " + token;

        axios.defaults.headers = axios.defaults.headers || {};
        axios.defaults.headers.common = axios.defaults.headers.common || {};
        axios.defaults.headers.common["Authorization"] = "Bearer " + token;

        // notify app
        window.dispatchEvent(new Event("user-changed"));

        // navigate immediately
        if (this.$root) this.$root.view = "UserDash";

        console.log("Login succeeded:", user);
      } catch (err) {
        console.error("Login error:", err);
        // unwrap common server error formats
        const msg =
          err?.response?.data?.error ||
          err?.response?.data?.message ||
          err?.message ||
          "Login failed";
        this.error = msg;
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>

<style scoped>
.card { margin-top: 40px; }
</style>
