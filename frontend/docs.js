"use strict";
// A self-hosted schema explorer keeps the API reference usable under the strict CSP.
const make = (tag, text, className) => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
};
fetch("/openapi.json", { credentials: "same-origin" })
  .then((r) => {
    if (!r.ok) throw new Error("Schema unavailable");
    return r.json();
  })
  .then((schema) => {
    const cards = [];
    for (const [path, methods] of Object.entries(schema.paths)) {
      for (const [method, spec] of Object.entries(methods)) {
        if (
          ![
            "get",
            "post",
            "put",
            "delete",
            "patch",
            "options",
            "head",
          ].includes(method)
        )
          continue;
        const card = make("details", "", "panel api-endpoint");
        const summary = make(
          "summary",
          `${method.toUpperCase()}  ${path} — ${spec.summary || ""}`,
        );
        card.append(
          summary,
          make(
            "p",
            spec.description || "See the request and response schema below.",
          ),
          make(
            "pre",
            JSON.stringify(
              {
                parameters: spec.parameters,
                requestBody: spec.requestBody,
                responses: spec.responses,
              },
              null,
              2,
            ),
          ),
        );
        document.getElementById("endpoints").append(card);
        cards.push(card);
      }
    }
    for (const [name, spec] of Object.entries(
      schema.components?.schemas || {},
    )) {
      const card = make("details", "", "panel api-endpoint");
      card.append(
        make("summary", name),
        make("pre", JSON.stringify(spec, null, 2)),
      );
      document.getElementById("schemas").append(card);
    }
    document
      .getElementById("endpoint-search")
      .addEventListener("input", (event) => {
        const query = event.target.value.toLowerCase();
        cards.forEach((c) => {
          c.hidden = !c.textContent.toLowerCase().includes(query);
        });
      });
  })
  .catch(() => {
    document.getElementById("docs-error").hidden = false;
  });
