/**
 * AI Operations Brain — the small markdown subset the work-order assistant replies in
 * (bold, italic, code, headings, lists), rendered without an external dependency.
 */

export function MdText({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let k = 0;
  let olItems: string[] = [];
  let ulItems: string[] = [];

  const flushOl = () => {
    if (!olItems.length) return;
    blocks.push(
      <ol key={k++} className="list-decimal list-inside space-y-0.5 pl-1">
        {olItems.map((t, i) => <li key={i}>{inlineFmt(t)}</li>)}
      </ol>
    );
    olItems = [];
  };
  const flushUl = () => {
    if (!ulItems.length) return;
    blocks.push(
      <ul key={k++} className="list-disc list-inside space-y-0.5 pl-1">
        {ulItems.map((t, i) => <li key={i}>{inlineFmt(t)}</li>)}
      </ul>
    );
    ulItems = [];
  };

  for (const raw of text.split("\n")) {
    const t = raw.trim();
    const olM = t.match(/^\d+\.\s+(.*)/);
    const ulM = t.match(/^[-*]\s+(.*)/);
    const hM  = t.match(/^#{1,3}\s+(.*)/);

    if (olM) { flushUl(); olItems.push(olM[1]); continue; }
    if (ulM) { flushOl(); ulItems.push(ulM[1]); continue; }

    flushOl(); flushUl();

    if (!t)  { blocks.push(<div key={k++} className="h-1" />); continue; }
    if (hM)  { blocks.push(<p key={k++} className="font-semibold text-[#e8e8e8] mt-1">{inlineFmt(hM[1])}</p>); continue; }
    blocks.push(<p key={k++}>{inlineFmt(t)}</p>);
  }
  flushOl(); flushUl();

  return <div className="space-y-1">{blocks}</div>;
}

function inlineFmt(text: string): React.ReactNode[] {
  // Split on **bold**, *italic*, `code`
  const parts = text.split(/(\*\*(?:[^*]|\*(?!\*))+\*\*|\*[^*]+\*|`[^`]+`)/);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={i} className="font-semibold text-[#f0f0f0]">{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2)
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={i} className="bg-[#2a2a2a] rounded px-1 font-mono text-amber-400 text-[10px]">{part.slice(1, -1)}</code>;
    return part;
  });
}
