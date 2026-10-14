// Local video decoder lifecycle. Every wait cleans up listeners and has a timeout.
function videoWait(video, events, ready, action, timeout=20000){
  return new Promise((resolve,reject)=>{
    let timer;
    function cleanup(){clearTimeout(timer);for(let event of events)video.removeEventListener(event,check);video.removeEventListener('error',failed)}
    function check(){if(ready()){cleanup();resolve()}}
    function failed(){cleanup();let code=video.error?.code;reject(Error('视频解码失败（'+(code||'未知')+'）：请尝试 H.264、8-bit、yuv420p 的 MP4'))}
    for(let event of events)video.addEventListener(event,check);
    video.addEventListener('error',failed);
    timer=setTimeout(()=>{cleanup();reject(Error('视频加载或定位超时。请重新选择视频；若仍失败，尝试在 Edge / Chrome 打开此页面。'))},timeout);
    try{action();check()}catch(error){cleanup();reject(error)}
  });
}
async function loadVideo(video,url){
  video.pause();video.removeAttribute('src');video.load();
  video.preload='auto';video.muted=true;
  await videoWait(video,['loadedmetadata','loadeddata','canplay'],()=>video.readyState>=2&&video.videoWidth>0&&Number.isFinite(video.duration),()=>{video.src=url;video.load()});
}
async function seek(video,time){
  if(video.readyState>=2&&!video.seeking&&Math.abs(video.currentTime-time)<.0001)return;
  await videoWait(video,['seeked','loadeddata','canplay'],()=>!video.seeking&&video.readyState>=2&&Math.abs(video.currentTime-time)<.05,()=>{video.currentTime=time});
}
