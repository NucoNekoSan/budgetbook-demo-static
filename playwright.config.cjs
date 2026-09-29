const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir:'./tests', testMatch:'**/*.spec.cjs', workers:1,
  use:{baseURL:'http://127.0.0.1:8787', headless:true, trace:'retain-on-failure'},
  webServer:{command:'node tests/static-server.cjs',url:'http://127.0.0.1:8787',reuseExistingServer:false},
});
