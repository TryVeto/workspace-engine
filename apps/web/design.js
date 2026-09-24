/* Reference documents use the same library and reader primitives. */
let designSources=[];
const designGroups=[['Design',''],['Brand',''],['Product','']];
function designItems(){return items.filter(i=>i.mode==='design')}
function designNavigate(group=''){navigate('design');currentGroup=group;renderLibrary(group);focusContent()}
function designSidebar(side){for(const [group]of designGroups)side.append(button(group,()=>designNavigate(group),currentGroup===group?'active':''))}
function renderDesignLibrary(){renderLibrary(currentGroup)}
function renderDesignReader(){renderReader()}
