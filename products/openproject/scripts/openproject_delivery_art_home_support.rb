# frozen_string_literal: true

module OpenprojectDeliveryArtHomeSupport
  module_function

  def render_description
    <<~TEXT.strip
      ## Purpose

      `Workspace Delivery ART` is the execution plane for accepted work that has
      moved out of `Workspace Proposals`.

      ## Use These Surfaces

      - `ART Dashboard`
        - at-a-glance view of active initiatives, committed objectives, active execution, blockers, owned risks, and deferred open work
      - `PM² Phase Board`
        - top-level initiative governance by `PM² Phase`, plus a separate `Retired` terminal lane
      - `ART Execution Kanban`
        - day-to-day execution flow for open delivery work
      - `PI Objectives`
        - committed-versus-stretch Program Increment objective visibility
      - `ART Risk Register`
        - ROAM risk tracking for the ART

      ## Operating Model

      - `Epic`
        - initiative-of-record
        - PM² governance lives here
      - child work items
        - SAFe-aligned execution records for `PI Objective`, `Feature`, `User story`, `Defect`, `Task`, `Milestone`, and `Risk`
        - `Enabler` and `Improvement` now live as `Execution Classification` on `Feature` or `User story`, not as structural types
      - boards
        - operator-facing orientation and live execution surfaces

      ## Status Meaning

      - `new`
        - captured but not yet ready for active execution
      - `ready`
        - execution-ready and eligible for the active front
      - `in-progress`
        - actively being worked
      - `blocked`
        - active work is impeded and needs an explicit decision path
      - `parked`
        - deferred open work that may return later
      - `retired`
        - terminal inactive work that should not return
      - `done`
        - completed with recorded evidence

      ## Delivery Truth

      - ART
        - work-state truth
      - owner repos
        - implementation and design truth
      - `workspace-governance`
        - workspace-control truth
    TEXT
  end
end
