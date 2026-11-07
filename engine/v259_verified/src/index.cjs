'use strict';
const engine = require('./underwrite.cjs');
const notes = require('./notes.cjs');
const assurance = require('./assurance.cjs');
const ENGINE_VERSION = require('../package.json').version;
module.exports = { ...engine, notes, assurance, ENGINE_VERSION };
