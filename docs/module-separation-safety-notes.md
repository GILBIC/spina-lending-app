# Module-separation safety notes

The current application has extensive shared state and callback wiring. Moving code can change import order, startup timing, object ownership, database connection use, and Tkinter thread behavior even when function bodies are unchanged.

For that reason, this planning stage intentionally selects no automatic move candidates. Later extraction PRs should remain small and reversible.
