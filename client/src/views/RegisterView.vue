<template>
  <div class="col-md-5 offset-md-3">
    <h3 class="mb-3">Register</h3>

    <form @submit.prevent="doRegister">
      <input v-model="username" class="form-control mb-2" placeholder="Username" required />

      <input v-model="email" class="form-control mb-2" placeholder="Email" required />

      <input v-model="password" type="password" class="form-control mb-3" placeholder="Password" required />

      <button class="btn btn-success w-100">Register</button>
    </form>
  </div>
</template>

<script>
export default {
  data() {
    return { username: "", email: "", password: "" };
  },

  methods: {
    async doRegister() {
      try {
        const r = await this.$axios.post("/auth/register", {
          username: this.username,
          email: this.email,
          password: this.password,
        });

        localStorage.setItem("token", r.data.token);
        localStorage.setItem("user", JSON.stringify(r.data.user));
        window.dispatchEvent(new Event("user-changed"));
        alert("Registered successfully!");
        if(this.$root)  this.$root.view = "UserDash";

      } catch (e) {
        alert("Registration failed.");
      }
    },
  },
};
</script>
