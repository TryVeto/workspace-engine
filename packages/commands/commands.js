/* One owner for section commands. Page actions retain unmodified keys. */
window.WorkspaceCommands=Object.freeze({
 sections:Object.freeze(['home','decisions','work','tasks','updates','company','design','prompts','skills']),
 navigationDigit(event){return event.altKey?/^(?:Digit|Numpad)([1-9])$/.exec(event.code)?.[1]:/^[1-9]$/.test(event.key)?event.key:null},
 isTyping(event){return event.composedPath().some(n=>n instanceof Element&&(n.matches('input,textarea,select,[contenteditable]')||n.isContentEditable))}
});
