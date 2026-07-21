// Minimal preload — sayt o'z JS bilan ishlaydi; Node API ochilmaydi.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('chaqmoqDesktop', {
  isDesktop: true,
  platform: process.platform,
});
