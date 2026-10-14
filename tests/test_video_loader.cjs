const fs=require('fs'),vm=require('vm'),assert=require('assert');
vm.runInThisContext(fs.readFileSync(require('path').join(__dirname,'../video-loader.js'),'utf8'));
class Video extends EventTarget{
  constructor(){super();this.readyState=0;this.videoWidth=0;this.duration=NaN;this.seeking=false;this._time=0;this.error=null;this.listeners=0}
  addEventListener(...args){this.listeners++;super.addEventListener(...args)}
  removeEventListener(...args){this.listeners--;super.removeEventListener(...args)}
  pause(){} removeAttribute(){this.src='';this.readyState=0}
  load(){if(this.src)queueMicrotask(()=>{this.readyState=2;this.videoWidth=1920;this.duration=4.461;this.dispatchEvent(new Event('loadeddata'))})}
  get currentTime(){return this._time}
  set currentTime(t){this.seeking=true;queueMicrotask(()=>{this._time=t;this.seeking=false;this.dispatchEvent(new Event('seeked'))})}
}
(async()=>{
 let v=new Video();await loadVideo(v,'blob:local');assert.equal(v.duration,4.461);assert.equal(v.listeners,0);
 for(let i=0;i<26;i++)await seek(v,i/6);
 assert.equal(v.listeners,0);assert.equal(v.currentTime,25/6);
 await loadVideo(v,'blob:second');assert.equal(v.listeners,0);
 await assert.rejects(videoWait(v,['seeked'],()=>false,()=>{},5),/超时/);assert.equal(v.listeners,0);
 await assert.rejects(videoWait(v,['seeked'],()=>false,()=>{v.error={code:3};v.dispatchEvent(new Event('error'))}),/解码失败/);assert.equal(v.listeners,0);
 await assert.rejects(videoWait(v,['seeked'],()=>false,()=>{throw Error('bad seek')}),/bad seek/);assert.equal(v.listeners,0);
 console.log('6 video lifecycle checks passed (mock decoder; not real browser decoding)');
})().catch(error=>{console.error(error);process.exitCode=1});
