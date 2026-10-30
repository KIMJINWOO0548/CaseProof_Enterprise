// Measure the actual light-theme status badges, composited on their white card.
() => {
 const tabler=[...document.styleSheets].find(sheet=>sheet.href?.includes('/static/vendor/tabler-1.7.3/tabler.min.css'));
 if(location.protocol==='about:'||!tabler||tabler.cssRules.length<100)throw Error('Tabler stylesheet absent: contrast check NOT RUN');
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
 const context=canvas.getContext('2d',{willReadFrequently:true});
 const rgb=color=>{context.fillStyle='white';context.fillRect(0,0,1,1);context.fillStyle=color;context.fillRect(0,0,1,1);return [...context.getImageData(0,0,1,1).data].slice(0,3);};
 const luminance=values=>values.map(value=>{value/=255;return value<=.04045?value/12.92:((value+.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
 const results=[];
 for(const color of ['green','red','yellow']){
  const badge=document.createElement('span');badge.className=`badge bg-${color}-lt text-${color}`;
  badge.style.position='fixed';badge.style.left='-10000px';badge.textContent='상태';document.body.append(badge);
  try{const style=getComputedStyle(badge),foreground=rgb(style.color),background=rgb(style.backgroundColor),a=luminance(foreground),b=luminance(background),contrast=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);results.push({color,foreground,background,contrast});}
  finally{badge.remove();}
 }
 return {passed:results.every(result=>result.contrast>=4.5),minimum:4.5,theme:'light, white surface',results};
}
