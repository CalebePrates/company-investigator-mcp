#!/usr/bin/env node
"use strict";

const { version } = require("../package.json");
const { run } = require("../lib/launcher.js");

run({ version });
