# -*- coding: utf-8 -*-

PAGE_HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReBEC AI Search</title>
<style>
:root{--bg:#f5f7fb;--card:#fff;--text:#172033;--muted:#687087;--line:#dce1ea;--accent:#1f5eff;--accent2:#eef3ff;--ok:#177245;--warn:#a15c00;--warnbg:#fff4df;--danger:#b42318;--shadow:0 8px 30px rgba(31,43,75,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:1200px;margin:0 auto;padding:24px}.header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px}.title{font-size:28px;font-weight:750;letter-spacing:-.02em}.subtitle{color:var(--muted);margin-top:4px}.mode{font-size:12px;padding:6px 10px;border-radius:999px;background:#fff1cc;color:#765400;border:1px solid #efd47e}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:18px;margin-bottom:16px}.search-row{display:grid;grid-template-columns:1fr auto;gap:10px}.query{width:100%;min-height:70px;border:1px solid #cfd6e3;border-radius:12px;padding:15px 16px;font-size:16px;resize:vertical;outline:none}.query:focus,input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(31,94,255,.12)}button{border:0;border-radius:10px;padding:11px 16px;font-weight:650;cursor:pointer}.primary{background:var(--accent);color:white}.secondary{background:var(--accent2);color:#214ea8}.ghost{background:white;border:1px solid var(--line);color:var(--text)}.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:12px}.lang{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}.lang button{border-radius:0;background:white;padding:8px 12px;display:flex;gap:6px;align-items:center}.lang button.active{background:var(--accent);color:white}.flag{font-size:18px;line-height:1}.advanced{display:none;margin-top:16px;border-top:1px solid var(--line);padding-top:16px}.advanced.open{display:block}.advanced-note{background:#f7f9fd;border:1px solid var(--line);padding:10px 12px;border-radius:10px;color:var(--muted);margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.field label{display:block;color:var(--muted);font-size:12px;font-weight:650;margin-bottom:5px}.field input,.field select{width:100%;height:42px;border:1px solid #cfd6e3;border-radius:9px;background:white;padding:0 10px}.field.wide{grid-column:span 2}.required-filter label::after{content:" •";color:var(--accent)}.stats{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);margin:4px 0 12px}.stats b{color:var(--text)}.result{border:1px solid var(--line);border-radius:13px;padding:15px;margin-bottom:10px;background:white}.result.primary-result{border-left:4px solid var(--accent)}.result.related-result{border-left:4px solid #b8bec9}.result-head{display:flex;gap:12px;align-items:flex-start}.result-title{font-size:17px;font-weight:700;margin-bottom:5px}.meta{display:flex;flex-wrap:wrap;gap:7px 12px;color:var(--muted);font-size:13px}.pill{display:inline-block;background:#f1f4f9;border-radius:999px;padding:4px 8px;font-size:12px}.warning-pill{display:inline-block;background:var(--warnbg);color:var(--warn);border:1px solid #f2c879;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:700}.actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.empty{padding:24px;text-align:center;color:var(--muted)}.debug{display:none}.debug.visible{display:block}.debug textarea{width:100%;height:420px;background:#0d1117;color:#d7e0ea;border:1px solid #273142;border-radius:10px;padding:14px;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre;resize:vertical}.debug-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}.debug-actions{display:flex;gap:8px;flex-wrap:wrap}.loading{display:none;color:var(--muted);margin-top:10px}.loading.visible{display:block}.pagination{display:flex;gap:8px;align-items:center;justify-content:center;margin:16px 0}.modal-bg{display:none;position:fixed;inset:0;background:rgba(13,20,34,.55);padding:30px;z-index:50;overflow:auto}.modal-bg.open{display:block}.modal{max-width:1000px;margin:0 auto;background:white;border-radius:16px;padding:20px}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.detail-section{border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff}.detail-section.full{grid-column:1/-1}.detail-section h3{margin:0 0 10px;font-size:15px}.detail-row{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:6px 0;border-bottom:1px solid #eef1f6}.detail-row:last-child{border-bottom:0}.detail-label{font-size:12px;font-weight:700;color:var(--muted)}.detail-value{word-break:break-word}.detail-link{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;border-radius:9px;padding:10px 14px;font-weight:700}.detail-list{margin:0;padding-left:20px}.small{font-size:12px;color:var(--muted)}.error{display:none;background:#fff2f0;border:1px solid #ffd5cf;color:#7a271a;border-radius:12px;padding:12px 14px;margin-top:12px;white-space:pre-wrap}.error.visible{display:block}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.wrap{padding:12px}.search-row{grid-template-columns:1fr}.grid,.detail-grid{grid-template-columns:1fr}.field.wide,.detail-section.full{grid-column:span 1}.header{align-items:flex-start}.title{font-size:23px}.lang button{padding:8px 9px}.detail-row{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div>
      <div class="title">ReBEC AI Search</div>
      <div id="subtitle" class="subtitle"></div>
    </div>
    <div class="mode">MODE: __APP_MODE__</div>
  </div>

  <div class="card">
    <div class="search-row">
      <textarea id="query" class="query"></textarea>
      <button id="searchBtn" class="primary"></button>
    </div>

    <div class="toolbar">
      <div class="lang">
        <button data-lang="pt" class="active"><span class="flag">🇧🇷</span><span>Português</span></button>
        <button data-lang="en"><span class="flag">🇺🇸</span><span>English</span></button>
        <button data-lang="es"><span class="flag">🇪🇸</span><span>Español</span></button>
      </div>
      <button id="advancedBtn" class="ghost"></button>
      <button id="clearBtn" class="ghost"></button>
      <span id="filterHelp" class="small"></span>
    </div>

    <div id="advanced" class="advanced">
      <div id="advancedNote" class="advanced-note"></div>
      <div class="grid">
        <div class="field wide"><label id="lblCondition"></label><input id="condition"></div>
        <div class="field wide"><label id="lblIntervention"></label><input id="intervention"></div>
        <div class="field wide"><label id="lblTitle"></label><input id="titleFilter"></div>
        <div class="field wide"><label id="lblSponsor"></label><input id="sponsor"></div>

        <div class="field required-filter"><label id="lblStudyType"></label><select id="studyType"><option value=""></option></select></div>
        <div class="field required-filter"><label id="lblRecruitment"></label><select id="recruitment"><option value=""></option></select></div>
        <div class="field required-filter"><label id="lblPhase"></label><select id="phase"><option value=""></option></select></div>
        <div class="field required-filter"><label id="lblGender"></label><select id="gender"><option value=""></option></select></div>

        <div class="field"><label id="lblAgeRange"></label><select id="agePreset"><option value=""></option><option value="0|17"></option><option value="18|59"></option><option value="60|"></option><option value="custom"></option></select></div>
        <div class="field"><label id="lblAgeMin"></label><input id="ageMin" type="number" min="0" step="1"></div>
        <div class="field"><label id="lblAgeMax"></label><input id="ageMax" type="number" min="0" step="1"></div>
        <div class="field required-filter"><label id="lblCountry"></label><select id="country"><option value=""></option></select></div>

        <div class="field"><label id="lblDateFrom"></label><input id="dateFrom" type="date"></div>
        <div class="field"><label id="lblDateTo"></label><input id="dateTo" type="date"></div>
        <div class="field"><label id="lblPageSize"></label><select id="pageSize"><option>10</option><option selected>20</option><option>30</option><option>50</option></select></div>
      </div>
    </div>

    <div id="loading" class="loading"></div>
    <div id="errorBox" class="error"></div>
  </div>

  <div id="resultsCard" class="card" style="display:none">
    <div class="toolbar" style="margin-top:0;justify-content:space-between">
      <div id="stats" class="stats"></div>
      <div>
        <button id="exportSelected" class="secondary"></button>
        <button id="exportAll" class="secondary"></button>
      </div>
    </div>
    <div id="results"></div>
    <div id="pagination" class="pagination"></div>
  </div>

  <div id="debugCard" class="card debug">
    <div class="debug-head">
      <b>DEBUG LOG</b>
      <div class="debug-actions">
        <button id="copyDebug" class="ghost"></button>
        <button id="downloadDebug" class="ghost"></button>
      </div>
    </div>
    <textarea id="debugLog" readonly spellcheck="false"></textarea>
    <div id="debugHelp" class="small"></div>
  </div>
</div>

<div id="modalBg" class="modal-bg">
  <div class="modal">
    <div class="toolbar" style="justify-content:space-between;margin-top:0">
      <b id="modalTitle"></b>
      <button id="closeModal" class="ghost"></button>
    </div>
    <div id="modalBody"></div>
  </div>
</div>

<script>
const BASE='/ai-search';
let language='pt';
let lastPayload=null;
let lastSearchId=null;
let currentPage=1;
let lastDebugText='';

const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const arr=v=>Array.isArray(v)?v:[];

const I18N={
pt:{
 subtitle:'Busca inteligente e avançada sobre a base ICTRP normalizada',
 placeholder:'Ex.: estudos usando exercícios físicos para idosos com problemas de equilíbrio',
 search:'Buscar',advanced:'Busca avançada ▾',clear:'Limpar',
 help:'Os filtros fechados são carregados diretamente do banco e também são enviados ao modelo como parte da intenção completa da busca.',
 advancedNote:'Campos marcados com • são listas fechadas obtidas diretamente dos valores presentes na base ICTRP.',
 condition:'Condição / doença',intervention:'Intervenção',title:'Título contém',sponsor:'Patrocinador',
 studyType:'Tipo de estudo',recruitment:'Situação do recrutamento',phase:'Fase',gender:'Sexo',ageRange:'Faixa etária',
 ageMin:'Idade mínima',ageMax:'Idade máxima',country:'País',dateFrom:'Registro desde',dateTo:'Registro até',pageSize:'Resultados por página',
 all:'Todos',allF:'Todas',children:'Crianças (0–17)',adults:'Adultos (18–59)',elderly:'Idosos (60+)',custom:'Personalizada',
 loading:'Processando busca…',exportSelected:'Exportar selecionados (ZIP)',exportAll:'Exportar todos (ZIP)',
 results:'resultados',primary:'principais',related:'relacionados',none:'Nenhum resultado nesta página.',
 details:'Detalhes',original:'Original',score:'score',phaseWord:'fase',genderWord:'sexo',primaryOne:'principal',relatedOne:'relacionado',
 prev:'← Anterior',next:'Próxima →',page:'Página',of:'de',copy:'Copiar log',download:'Baixar log (.txt)',copied:'Copiado',
 debugHelp:'Clique na caixa e use Ctrl+A / Ctrl+C, ou use os botões acima.',
 close:'Fechar',selectOne:'Selecione ao menos um ensaio.',searchError:'Erro na busca',exportError:'Erro ao exportar',detailError:'Erro ao abrir detalhes',
 stale:'Possivelmente desatualizado',staleHelp:'A data real de inclusão tem mais de um ano e o estudo ainda aparece com recrutamento aberto.',
 openRecord:'Abrir registro',openRecordShort:'Abrir registro ↗',identification:'Identificação',study:'Estudo',recruitmentSection:'Recrutamento e população',
 clinical:'Condição e intervenção',outcomes:'Desfechos',eligibility:'Elegibilidade',countries:'Países',
 registry:'Registro',trialId:'ID do ensaio',utrn:'UTRN',publicTitle:'Título público',scientificTitle:'Título científico',
 sponsorLabel:'Patrocinador principal',studyTypeLabel:'Tipo de estudo',studyDesign:'Desenho do estudo',phaseLabel:'Fase',
 recruitmentLabel:'Situação do recrutamento',enrolmentDate:'Data de inclusão',enrolmentType:'Tipo da data de inclusão',
 targetSize:'Tamanho da amostra',sex:'Sexo',age:'Idade',conditionLabel:'Condição',interventionLabel:'Intervenção',
 inclusion:'Critérios de inclusão',exclusion:'Critérios de exclusão',primaryOutcomes:'Desfechos primários',secondaryOutcomes:'Desfechos secundários'
},
en:{
 subtitle:'Intelligent and advanced search over the normalized ICTRP database',
 placeholder:'E.g. studies using physical exercise for older adults with balance problems',
 search:'Search',advanced:'Advanced search ▾',clear:'Clear',
 help:'Closed filters are loaded directly from the database and are also sent to the model as part of the complete search intent.',
 advancedNote:'Fields marked with • are closed lists populated directly from values present in the ICTRP database.',
 condition:'Condition / disease',intervention:'Intervention',title:'Title contains',sponsor:'Sponsor',
 studyType:'Study type',recruitment:'Recruitment status',phase:'Phase',gender:'Sex',ageRange:'Age range',
 ageMin:'Minimum age',ageMax:'Maximum age',country:'Country',dateFrom:'Registered from',dateTo:'Registered to',pageSize:'Results per page',
 all:'All',allF:'All',children:'Children (0–17)',adults:'Adults (18–59)',elderly:'Older adults (60+)',custom:'Custom',
 loading:'Processing search…',exportSelected:'Export selected (ZIP)',exportAll:'Export all (ZIP)',
 results:'results',primary:'primary',related:'related',none:'No results on this page.',
 details:'Details',original:'Original',score:'score',phaseWord:'phase',genderWord:'sex',primaryOne:'primary',relatedOne:'related',
 prev:'← Previous',next:'Next →',page:'Page',of:'of',copy:'Copy log',download:'Download log (.txt)',copied:'Copied',
 debugHelp:'Click the box and use Ctrl+A / Ctrl+C, or use the buttons above.',
 close:'Close',selectOne:'Select at least one trial.',searchError:'Search error',exportError:'Export error',detailError:'Error opening details',
 stale:'Possibly outdated',staleHelp:'The actual enrolment date is more than one year old and the study still shows open recruitment.',
 openRecord:'Open registry record',openRecordShort:'Open record ↗',identification:'Identification',study:'Study',recruitmentSection:'Recruitment and population',
 clinical:'Condition and intervention',outcomes:'Outcomes',eligibility:'Eligibility',countries:'Countries',
 registry:'Registry',trialId:'Trial ID',utrn:'UTRN',publicTitle:'Public title',scientificTitle:'Scientific title',
 sponsorLabel:'Primary sponsor',studyTypeLabel:'Study type',studyDesign:'Study design',phaseLabel:'Phase',
 recruitmentLabel:'Recruitment status',enrolmentDate:'Enrolment date',enrolmentType:'Enrolment date type',
 targetSize:'Target size',sex:'Sex',age:'Age',conditionLabel:'Condition',interventionLabel:'Intervention',
 inclusion:'Inclusion criteria',exclusion:'Exclusion criteria',primaryOutcomes:'Primary outcomes',secondaryOutcomes:'Secondary outcomes'
},
es:{
 subtitle:'Búsqueda inteligente y avanzada sobre la base ICTRP normalizada',
 placeholder:'Ej.: estudios con ejercicio físico para adultos mayores con problemas de equilibrio',
 search:'Buscar',advanced:'Búsqueda avanzada ▾',clear:'Limpiar',
 help:'Los filtros cerrados se cargan directamente de la base y también se envían al modelo como parte de la intención completa.',
 advancedNote:'Los campos marcados con • son listas cerradas obtenidas directamente de los valores presentes en la base ICTRP.',
 condition:'Condición / enfermedad',intervention:'Intervención',title:'Título contiene',sponsor:'Patrocinador',
 studyType:'Tipo de estudio',recruitment:'Estado de reclutamiento',phase:'Fase',gender:'Sexo',ageRange:'Rango de edad',
 ageMin:'Edad mínima',ageMax:'Edad máxima',country:'País',dateFrom:'Registro desde',dateTo:'Registro hasta',pageSize:'Resultados por página',
 all:'Todos',allF:'Todas',children:'Niños (0–17)',adults:'Adultos (18–59)',elderly:'Adultos mayores (60+)',custom:'Personalizada',
 loading:'Procesando búsqueda…',exportSelected:'Exportar seleccionados (ZIP)',exportAll:'Exportar todos (ZIP)',
 results:'resultados',primary:'principales',related:'relacionados',none:'No hay resultados en esta página.',
 details:'Detalles',original:'Original',score:'score',phaseWord:'fase',genderWord:'sexo',primaryOne:'principal',relatedOne:'relacionado',
 prev:'← Anterior',next:'Siguiente →',page:'Página',of:'de',copy:'Copiar log',download:'Descargar log (.txt)',copied:'Copiado',
 debugHelp:'Haga clic en el cuadro y use Ctrl+A / Ctrl+C, o use los botones.',
 close:'Cerrar',selectOne:'Seleccione al menos un ensayo.',searchError:'Error en la búsqueda',exportError:'Error al exportar',detailError:'Error al abrir detalles',
 stale:'Posiblemente desactualizado',staleHelp:'La fecha real de inclusión tiene más de un año y el estudio todavía muestra reclutamiento abierto.',
 openRecord:'Abrir registro',openRecordShort:'Abrir registro ↗',identification:'Identificación',study:'Estudio',recruitmentSection:'Reclutamiento y población',
 clinical:'Condición e intervención',outcomes:'Desenlaces',eligibility:'Elegibilidad',countries:'Países',
 registry:'Registro',trialId:'ID del ensayo',utrn:'UTRN',publicTitle:'Título público',scientificTitle:'Título científico',
 sponsorLabel:'Patrocinador principal',studyTypeLabel:'Tipo de estudio',studyDesign:'Diseño del estudio',phaseLabel:'Fase',
 recruitmentLabel:'Estado de reclutamiento',enrolmentDate:'Fecha de inclusión',enrolmentType:'Tipo de fecha de inclusión',
 targetSize:'Tamaño de la muestra',sex:'Sexo',age:'Edad',conditionLabel:'Condición',interventionLabel:'Intervención',
 inclusion:'Criterios de inclusión',exclusion:'Criterios de exclusión',primaryOutcomes:'Desenlaces primarios',secondaryOutcomes:'Desenlaces secundarios'
}};

function t(k){return (I18N[language]||I18N.pt)[k]||k}
function setFirstOption(id,text){const s=$(id);if(s&&s.options.length)s.options[0].textContent=text}
function optionLabel(kind,value){
 const v=String(value||'');
 const n=v.toLowerCase();
 if(kind==='studyType'){
   if(n.includes('intervention'))return language==='pt'?'Intervenção':language==='es'?'Intervención':'Intervention';
   if(n.includes('observ'))return language==='pt'?'Observacional':language==='es'?'Observacional':'Observational';
 }
 if(kind==='gender'){
   if(n==='f'||n==='female')return language==='pt'?'Feminino':language==='es'?'Femenino':'Female';
   if(n==='m'||n==='male')return language==='pt'?'Masculino':language==='es'?'Masculino':'Male';
   if(n==='-'||n.includes('both')||n==='all')return language==='pt'?'Ambos':language==='es'?'Ambos':'Both';
 }
 if(kind==='recruitment'){
   const map={
    'recruiting':{pt:'Recrutando',en:'Recruiting',es:'Reclutando'},
    'not yet recruiting':{pt:'Ainda não recrutando',en:'Not yet recruiting',es:'Aún no reclutando'},
    'recruitment completed':{pt:'Recrutamento concluído',en:'Recruitment completed',es:'Reclutamiento completado'},
    'data analysis completed':{pt:'Análise de dados concluída',en:'Data analysis completed',es:'Análisis de datos completado'},
    'suspended':{pt:'Suspenso',en:'Suspended',es:'Suspendido'},
    'terminated':{pt:'Encerrado',en:'Terminated',es:'Terminado'},
    'withdrawn':{pt:'Retirado',en:'Withdrawn',es:'Retirado'}
   };
   return map[n]?.[language]||v;
 }
 return v;
}
function refreshOptionLabels(){
 [['studyType','studyType'],['recruitment','recruitment'],['gender','gender']].forEach(([id,kind])=>{
   const sel=$(id); [...sel.options].slice(1).forEach(o=>o.textContent=optionLabel(kind,o.value));
 });
}
function applyLanguage(){
 document.documentElement.lang=language==='pt'?'pt-BR':language;
 $('subtitle').textContent=t('subtitle');$('query').placeholder=t('placeholder');$('searchBtn').textContent=t('search');
 $('advancedBtn').textContent=t('advanced');$('clearBtn').textContent=t('clear');$('filterHelp').textContent=t('help');$('advancedNote').textContent=t('advancedNote');
 $('lblCondition').textContent=t('condition');$('lblIntervention').textContent=t('intervention');$('lblTitle').textContent=t('title');$('lblSponsor').textContent=t('sponsor');
 $('lblStudyType').textContent=t('studyType');$('lblRecruitment').textContent=t('recruitment');$('lblPhase').textContent=t('phase');$('lblGender').textContent=t('gender');
 $('lblAgeRange').textContent=t('ageRange');$('lblAgeMin').textContent=t('ageMin');$('lblAgeMax').textContent=t('ageMax');$('lblCountry').textContent=t('country');
 $('lblDateFrom').textContent=t('dateFrom');$('lblDateTo').textContent=t('dateTo');$('lblPageSize').textContent=t('pageSize');
 $('loading').textContent=t('loading');$('exportSelected').textContent=t('exportSelected');$('exportAll').textContent=t('exportAll');
 $('copyDebug').textContent=t('copy');$('downloadDebug').textContent=t('download');$('debugHelp').textContent=t('debugHelp');$('closeModal').textContent=t('close');
 setFirstOption('studyType',t('all'));setFirstOption('recruitment',t('all'));setFirstOption('phase',t('allF'));setFirstOption('gender',t('all'));setFirstOption('country',t('all'));
 const a=$('agePreset').options;a[0].textContent=t('allF');a[1].textContent=t('children');a[2].textContent=t('adults');a[3].textContent=t('elderly');a[4].textContent=t('custom');
 refreshOptionLabels();
}
function addOptions(id,values){const s=$(id);values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o)})}
async function loadOptions(){
 try{
   const r=await fetch(BASE+'/api/options');
   let d={};
   try{ d=await r.json(); }catch(_){}

   if(!r.ok){
     const msg=(d&&d.detail)
       ? (typeof d.detail==='string'
          ? d.detail
          : JSON.stringify(d.detail))
       : `HTTP ${r.status} ao carregar filtros`;
     throw new Error(msg);
   }

   if(!d || !d.options){
     throw new Error(
       'Resposta inválida de /api/options: campo "options" ausente'
     );
   }

   addOptions(
     'studyType',
     d.options.study_type||[]
   );
   addOptions(
     'recruitment',
     d.options.recruitment_status||[]
   );
   addOptions(
     'phase',
     d.options.phase||[]
   );
   addOptions(
     'gender',
     d.options.gender||[]
   );
   addOptions(
     'country',
     d.options.country||[]
   );

   applyLanguage();

 }catch(e){
   showError(
     'Falha ao carregar filtros avançados: '+
     (e.message||e)
   );
 }
}
function val(id){const v=$(id).value.trim();return v===''?null:v}
function num(id){const v=val(id);return v===null?null:Number(v)}
function buildPayload(page=1){
 return{
  query:val('query')||'',language,
  filters:{
   condition:val('condition'),intervention:val('intervention'),title:val('titleFilter'),sponsor:val('sponsor'),
   study_type:val('studyType'),recruitment_status:val('recruitment'),phase:val('phase'),gender:val('gender'),
   age_min_years:num('ageMin'),age_max_years:num('ageMax'),country:val('country'),
   registration_date_from:val('dateFrom'),registration_date_to:val('dateTo')
  },
  page,page_size:Number($('pageSize').value),threshold:.70
 }
}
function showError(msg){$('errorBox').textContent=msg;$('errorBox').classList.add('visible')}
function clearError(){$('errorBox').classList.remove('visible');$('errorBox').textContent=''}
function renderDebugText(text){lastDebugText=text||'';if(lastDebugText){$('debugCard').classList.add('visible');$('debugLog').value=lastDebugText}else{$('debugCard').classList.remove('visible')}}
async function runSearch(page=1){
 $('loading').classList.add('visible');
 $('searchBtn').disabled=true;
 clearError();

 try{
  let r;
  let d;

  if(lastSearchId && page!==1){
    const pageSize=Number($('pageSize').value);

    r=await fetch(
      BASE+
      '/api/search/'+
      encodeURIComponent(lastSearchId)+
      '/page?page='+
      encodeURIComponent(page)+
      '&page_size='+
      encodeURIComponent(pageSize)
    );

    d=await r.json();

  }else{
    lastPayload=buildPayload(page);

    r=await fetch(
      BASE+'/api/search',
      {
        method:'POST',
        headers:{
          'Content-Type':'application/json'
        },
        body:JSON.stringify(lastPayload)
      }
    );

    d=await r.json();
  }

  if(!r.ok){
    const detail=d.detail||{};

    showError(
      typeof detail==='string'
        ? detail
        : (detail.message||t('searchError'))
    );

    if(detail.debug_log){
      renderDebugText(detail.debug_log);
    }

    return;
  }

  if(d.search_id){
    lastSearchId=d.search_id;
  }

  currentPage=d.page;
  renderResults(d);
  renderDebug(d);

 }catch(e){
  showError(e.message||t('searchError'));
 }finally{
  $('loading').classList.remove('visible');
  $('searchBtn').disabled=false;
 }
}
function staleBadge(x){
 return x?.recruitment_freshness?.possibly_outdated
   ? `<span class="warning-pill" title="${esc(t('staleHelp'))}">⚠ ${esc(t('stale'))}</span>`
   : '';
}
function renderResults(d){
 $('resultsCard').style.display='block';
 $('stats').innerHTML=`<span><b>${d.total_results}</b> ${t('results')}</span><span><b>${d.primary_count}</b> ${t('primary')}</span><span><b>${d.related_count}</b> ${t('related')}</span><span>MySQL+ranking: <b>${d.db_stats.total_search_seconds}s</b></span>`;
 const box=$('results');box.innerHTML='';
 if(!d.results.length)box.innerHTML=`<div class="empty">${esc(t('none'))}</div>`;
 d.results.forEach(x=>{
  const div=document.createElement('div');div.className='result '+(x.result_class==='primary'?'primary-result':'related-result');
  div.innerHTML=`<div class="result-head"><input type="checkbox" class="trialCheck" value="${esc(x.trial_id)}"><div style="flex:1">
   <div class="result-title">${esc(x.public_title||'(sem título)')}</div>
   ${x.public_title_original&&x.public_title_original!==x.public_title?`<div class="small">${esc(t('original'))}: ${esc(x.public_title_original)}</div>`:''}
   <div class="meta"><span><b>${esc(x.trial_id)}</b></span><span>${esc(t('score'))} ${Number(x.score||0).toFixed(2)}</span><span>${esc(x.recruitment_status||'')}</span><span>${esc(t('phaseWord'))} ${esc(x.phase||'N/A')}</span><span>${esc(t('genderWord'))} ${esc(x.gender||'-')}</span><span>${esc(x.date_registration||'')}</span></div>
   <div style="margin-top:7px">${esc(x.health_condition||'')}</div>
   <div class="actions"><button class="ghost" onclick="showDetail('${esc(x.trial_id)}')">${esc(t('details'))}</button>${x.registration_url?`<a class="detail-link" style="padding:9px 12px" href="${esc(x.registration_url)}" target="_blank" rel="noopener noreferrer">${esc(t('openRecordShort'))}</a>`:''}<button class="ghost" onclick="window.open(BASE+'/api/trials/${encodeURIComponent(x.trial_id)}/xml','_blank')">XML</button>${staleBadge(x)}<span class="pill">${x.result_class==='primary'?esc(t('primaryOne')):esc(t('relatedOne'))}</span></div>
  </div></div>`;
  box.appendChild(div)
 });
 renderPagination(d.page,d.page_size,d.total_results)
}
function renderPagination(page,size,total){
 const pages=Math.max(1,Math.ceil(total/size)),p=$('pagination');p.innerHTML='';
 const prev=document.createElement('button');prev.className='ghost';prev.textContent=t('prev');prev.disabled=page<=1;prev.onclick=()=>runSearch(page-1);p.appendChild(prev);
 const s=document.createElement('span');s.textContent=`${t('page')} ${page} ${t('of')} ${pages}`;p.appendChild(s);
 const next=document.createElement('button');next.className='ghost';next.textContent=t('next');next.disabled=page>=pages;next.onclick=()=>runSearch(page+1);p.appendChild(next)
}
function renderDebug(d){if(d.debug&&d.debug.enabled)renderDebugText(d.debug.text||'')}
function detailRow(label,value){
 if(value===null||value===undefined||value===''||(Array.isArray(value)&&!value.length))return '';
 const shown=Array.isArray(value)?value.join('; '):value;
 return `<div class="detail-row"><div class="detail-label">${esc(label)}</div><div class="detail-value">${esc(shown)}</div></div>`;
}
function listHtml(values){
 const a=arr(values);if(!a.length)return '<span class="small">-</span>';
 return `<ul class="detail-list">${a.map(v=>`<li>${esc(typeof v==='object'?JSON.stringify(v):v)}</li>`).join('')}</ul>`;
}
async function showDetail(id){
 clearError();
 try{
  const r=await fetch(BASE+'/api/trials/'+encodeURIComponent(id));const d=await r.json();
  if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:t('detailError'));
  $('modalTitle').textContent=id;
  const warning=d.recruitment_freshness?.possibly_outdated
    ? `<div class="advanced-note" style="background:var(--warnbg);color:var(--warn);border-color:#f2c879"><b>⚠ ${esc(t('stale'))}</b><br>${esc(t('staleHelp'))}</div>`
    : '';
  const link=d.registration_url
    ? `<a class="detail-link" href="${esc(d.registration_url)}" target="_blank" rel="noopener">${esc(t('openRecord'))} ↗</a>`
    : '';
  $('modalBody').innerHTML=`
   ${warning}
   <div style="margin:12px 0">${link}</div>
   <div class="detail-grid">
    <section class="detail-section">
      <h3>${esc(t('identification'))}</h3>
      ${detailRow(t('trialId'),d.trial_id)}
      ${detailRow(t('utrn'),d.utrn)}
      ${detailRow(t('registry'),d.registry_name)}
      ${detailRow(t('sponsorLabel'),d.primary_sponsor)}
      ${detailRow('Data de registro',d.date_registration||d.date_registration_raw)}
    </section>
    <section class="detail-section">
      <h3>${esc(t('study'))}</h3>
      ${detailRow(t('studyTypeLabel'),d.study_type_raw||d.study_type)}
      ${detailRow(t('phaseLabel'),d.phase_raw||d.phase)}
      ${detailRow(t('publicTitle'),d.public_title)}
      ${detailRow(t('scientificTitle'),d.scientific_title)}
      ${detailRow(t('studyDesign'),d.study_design)}
    </section>
    <section class="detail-section">
      <h3>${esc(t('recruitmentSection'))}</h3>
      ${detailRow(t('recruitmentLabel'),d.recruitment_status_raw||d.recruitment_status)}
      ${detailRow(t('enrolmentDate'),d.date_enrolment||d.date_enrolment_raw)}
      ${detailRow(t('enrolmentType'),d.type_enrolment)}
      ${detailRow(t('targetSize'),d.target_size||d.target_size_raw)}
      ${detailRow(t('sex'),d.gender_raw||d.gender)}
      ${detailRow(t('age'),`${d.age_min_raw||d.age_min_years||'-'} — ${d.age_max_raw||d.age_max_years||'-'}`)}
      ${detailRow(t('countries'),d.countries)}
    </section>
    <section class="detail-section">
      <h3>${esc(t('clinical'))}</h3>
      ${detailRow(t('conditionLabel'),d.hc_freetext)}
      ${detailRow(t('interventionLabel'),d.i_freetext)}
      ${detailRow('Condition keywords',d.condition_keywords)}
      ${detailRow('Intervention keywords',d.intervention_keywords)}
    </section>
    <section class="detail-section full">
      <h3>${esc(t('eligibility'))}</h3>
      ${detailRow(t('inclusion'),d.inclusion_criteria)}
      ${detailRow(t('exclusion'),d.exclusion_criteria)}
    </section>
    <section class="detail-section full">
      <h3>${esc(t('outcomes'))}</h3>
      <div class="detail-row"><div class="detail-label">${esc(t('primaryOutcomes'))}</div><div class="detail-value">${listHtml(d.primary_outcomes)}</div></div>
      <div class="detail-row"><div class="detail-label">${esc(t('secondaryOutcomes'))}</div><div class="detail-value">${listHtml(d.secondary_outcomes)}</div></div>
    </section>
   </div>`;
  $('modalBg').classList.add('open');
 }catch(e){showError(e.message||t('detailError'))}
}
async function exportZip(scope){
 if(!lastSearchId)return;
 let ids=[];
 if(scope==='selected'){ids=[...document.querySelectorAll('.trialCheck:checked')].map(x=>x.value);if(!ids.length){showError(t('selectOne'));return}}
 const r=await fetch(BASE+'/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({search_id:lastSearchId,scope,trial_ids:ids})});
 if(!r.ok){const d=await r.json();showError((d.detail&&d.detail.message)||d.detail||t('exportError'));return}
 const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='rebec_ai_search.zip';document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href)
}
function downloadDebug(){
 if(!lastDebugText)return;const blob=new Blob([lastDebugText],{type:'text/plain;charset=utf-8'});const a=document.createElement('a');
 a.href=URL.createObjectURL(blob);a.download=`rebec_ai_debug_${new Date().toISOString().replace(/[:.]/g,'-')}.txt`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(a.href)
}

$('advancedBtn').onclick=()=>$('advanced').classList.toggle('open');
$('searchBtn').onclick=()=>{
 lastSearchId=null;
 runSearch(1);
};
$('query').addEventListener(
 'keydown',
 e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){
   lastSearchId=null;
   runSearch(1);
  }
 }
);
document.querySelectorAll('.lang button').forEach(b=>b.onclick=()=>{language=b.dataset.lang;document.querySelectorAll('.lang button').forEach(x=>x.classList.toggle('active',x===b));applyLanguage()});
$('agePreset').onchange=e=>{const v=e.target.value;if(v==='custom'||!v)return;const [a,b]=v.split('|');$('ageMin').value=a;$('ageMax').value=b};
$('clearBtn').onclick=()=>location.reload();
$('copyDebug').onclick=async()=>{try{await navigator.clipboard.writeText($('debugLog').value);$('copyDebug').textContent=t('copied');setTimeout(()=>$('copyDebug').textContent=t('copy'),1200)}catch(_){$('debugLog').focus();$('debugLog').select();document.execCommand('copy')}};
$('downloadDebug').onclick=downloadDebug;
$('exportSelected').onclick=()=>exportZip('selected');$('exportAll').onclick=()=>exportZip('all');
$('closeModal').onclick=()=>$('modalBg').classList.remove('open');$('modalBg').onclick=e=>{if(e.target===$('modalBg'))$('modalBg').classList.remove('open')};


[
 'condition','intervention','titleFilter','sponsor',
 'studyType','recruitment','phase','gender',
 'agePreset','ageMin','ageMax','country',
 'dateFrom','dateTo','pageSize'
].forEach(id=>{
 const el=$(id);
 if(el){
  el.addEventListener(
   'change',
   ()=>{lastSearchId=null;}
  );
 }
});

$('query').addEventListener(
 'input',
 ()=>{lastSearchId=null;}
);

applyLanguage();
loadOptions();
</script>
</body>
</html>'''
