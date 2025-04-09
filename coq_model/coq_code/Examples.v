From Coq Require Import Floats.Floats.
From Coq Require Import Lists.List.
From Coq Require Import Strings.String.
From Coq Require Import Strings.Ascii.
From Coq Require Import Structures.OrderedTypeEx.
Require Import FMapAVL.

Module StrMap := FMapAVL.Make(String_as_OT).
Open Scope string_scope.
Definition empty_map : StrMap.t nat := StrMap.empty nat.
Definition map1 : StrMap.t nat := StrMap.add "foo" 42 empty_map.