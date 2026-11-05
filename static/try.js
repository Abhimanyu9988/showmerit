// Try-it box: asks GitHub directly from the visitor's browser. ShowMerit stores nothing.
(() => {
  const form = document.getElementById("try-form");
  const input = document.getElementById("try-user");
  const out = document.getElementById("try-result");
  const months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
  const short = (date) => `${months[Number(date.slice(5, 7)) - 1]} ${Number(date.slice(8, 10))}`;
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  const say = (text) => out.replaceChildren(el("p", "note", text));

  function plain(title) {
    const scopes = [];
    let rest = title.trim();
    for (let tag = rest.match(/^\[([^\]]+)\]\s*/); tag; tag = rest.match(/^\[([^\]]+)\]\s*/)) {
      scopes.push(tag[1]);
      rest = rest.slice(tag[0].length);
    }
    const prefix = rest.match(/^(?:docs|fix|feat|chore)\(([^)]+)\):\s*|^([a-z0-9-]+\/[a-z0-9_-]+):\s*/);
    if (prefix) {
      scopes.push(prefix[1] || prefix[2]);
      rest = rest.slice(prefix[0].length);
    }
    return [rest.charAt(0).toUpperCase() + rest.slice(1), scopes.filter((s) => s !== "chore").join(" / ")];
  }

  function row(item) {
    const repo = item.repository_url.split("/repos/")[1];
    const name = repo.split("/")[1];
    const [title, scope] = plain(item.title);
    const owner = /code owner/i.test(item.title);
    const li = el("li");
    const claim = el("div", "claim", title);
    claim.append(el("small", "", scope ? `${repo} / ${scope}` : repo));
    const stub = el("a", owner ? "stub owner" : "stub");
    stub.href = item.html_url;
    stub.append(el("span", "", `${name} #${item.number}`), el("span", "", short(item.closed_at)));
    li.append(claim, stub);
    return li;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const user = input.value.trim().replace(/^@/, "");
    if (!/^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$/i.test(user)) {
      say("Enter a GitHub username, such as torvalds.");
      return;
    }
    say("Finding your merged work on GitHub...");
    const query = encodeURIComponent(`author:${user} is:pr is:merged -user:${user}`);
    try {
      const response = await fetch(`https://api.github.com/search/issues?q=${query}&per_page=30&sort=updated`,
        { headers: { Accept: "application/vnd.github+json" } });
      if (response.status === 403 || response.status === 429) {
        say("GitHub needs a short pause. Try again in a minute.");
        return;
      }
      if (response.status === 422) {
        say(`We couldn't find ${user} on GitHub. Check the spelling and try again.`);
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const found = await response.json();
      if (!found.items.length) {
        say(`${user} has no merged pull requests in other people's projects yet. Your first one will show here.`);
        return;
      }
      const shown = found.items.slice(0, 8);
      const summary = el("p", "lead", `${found.total_count} merged pull requests in other people's projects. Showing the ${shown.length} most recent.`);
      const list = el("ul", "ledger");
      list.append(...shown.map(row));
      const next = el("p", "note", "This preview isn't saved. Sign-up isn't open yet.");
      out.replaceChildren(el("h2", "", `${user}'s proof`), summary, list, next);
    } catch {
      say("GitHub didn't answer. Try again in a moment.");
    }
  });
})();
