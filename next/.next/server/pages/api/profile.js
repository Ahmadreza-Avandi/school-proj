"use strict";(()=>{var e={};e.id=7925,e.ids=[7925],e.modules={20145:e=>{e.exports=require("next/dist/compiled/next-server/pages-api.runtime.prod.js")},99648:e=>{e.exports=import("axios")},56249:(e,t)=>{Object.defineProperty(t,"l",{enumerable:!0,get:function(){return function e(t,r){return r in t?t[r]:"then"in t&&"function"==typeof t.then?t.then(t=>e(t,r)):"function"==typeof t&&"default"===r?t:void 0}}})},3857:(e,t,r)=>{r.a(e,async(e,a)=>{try{r.r(t),r.d(t,{config:()=>l,default:()=>d,routeModule:()=>c});var n=r(71802),o=r(47153),i=r(56249),s=r(33839),u=e([s]);s=(u.then?(await u)():u)[0];let d=(0,i.l)(s,"default"),l=(0,i.l)(s,"config"),c=new n.PagesAPIRouteModule({definition:{kind:o.x.PAGES_API,page:"/api/profile",pathname:"/api/profile",bundlePath:"",filename:""},userland:s});a()}catch(e){a(e)}})},33839:(e,t,r)=>{r.a(e,async(e,a)=>{try{r.r(t),r.d(t,{default:()=>i});var n=r(99648),o=e([n]);n=(o.then?(await o)():o)[0];let s="http://localhost:3001/users";async function i(e,t){let r=e.headers.authorization?.split(" ")[1];if(!r)return t.status(401).json({message:"Unauthorized"});try{if("GET"===e.method){let e=await n.default.get(s,{headers:{Authorization:`Bearer ${r}`}});return t.status(200).json(e.data)}if("PUT"!==e.method)return t.setHeader("Allow",["GET","PUT"]),t.status(405).end(`Method ${e.method} Not Allowed`);{let a=await n.default.put(s,e.body,{headers:{Authorization:`Bearer ${r}`}});return t.status(200).json(a.data)}}catch(a){console.error("Error fetching or updating profile:",a);let e=a.response?.status||500,r=a.response?.data?.message||"An error occurred while processing your request";t.status(e).json({error:r})}}a()}catch(e){a(e)}})},47153:(e,t)=>{var r;Object.defineProperty(t,"x",{enumerable:!0,get:function(){return r}}),function(e){e.PAGES="PAGES",e.PAGES_API="PAGES_API",e.APP_PAGE="APP_PAGE",e.APP_ROUTE="APP_ROUTE"}(r||(r={}))},71802:(e,t,r)=>{e.exports=r(20145)}};var t=require("../../webpack-api-runtime.js");t.C(e);var r=t(t.s=3857);module.exports=r})();