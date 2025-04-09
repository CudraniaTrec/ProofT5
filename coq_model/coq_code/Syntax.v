Set Warnings "-deprecated-hint-without-locality,-parsing".
Require Export Floats.Floats.
Require Export Lists.List.
Require Export Strings.String.
Require Export Structures.OrderedTypeEx.
Require Export FMapAVL.

(* reserved keywords *)
Definition this : string := "this".
Definition return' : string := "return".
Definition constructor : string := "Constructor".

(* Program Types *)
Inductive Ty : Type :=
    (* basic types *)
    | TyInt : Ty
    | TyFloat : Ty
    | TyBool : Ty
    | TyChar : Ty
    | TyString : Ty
    (* advanced types *)
    | TyArray : Ty->Ty                (* T[] *)
    | TyGeneric0 : string->Ty         (* s<> *)
    | TyGeneric1 : string->Ty->Ty     (* s<T> *)
    | TyGeneric2 : string->Ty->Ty->Ty (* s<T1,T2> *)
    | TyArrow : Ty->Ty->Ty            (* T1 -> T2 *)
    | TyClass : string->Ty            (* class T *)
    | TyVoid : Ty                     (* nil *)
    | TyConcat : Ty->Ty->Ty           (* T1::T2 *).

(* Evaluation context *)
Module StrMap := FMapAVL.Make(String_as_OT).
Definition ClassType : Type := StrMap.t Ty. (* field_name -> Ty *)
Record Context : Type := {
    var_type : StrMap.t Ty;                 (* var_name -> Ty*)
    class_type : StrMap.t ClassType;        (* class_name -> ClassType *)
}.

Notation "( x |-> y ; gamma )" := {|
    var_type := StrMap.add x y gamma.(var_type);
    class_type := gamma.(class_type)
|}.
Notation "m !! x" := (StrMap.find x m) (at level 100, x constr at level 0).
Declare Custom Entry IMPP_Ty.
Notation "<( e )>" := e (e custom IMPP_Ty at level 99).
Notation "( x )" := x (in custom IMPP_Ty, x constr at level 99).
Notation "x" := x (in custom IMPP_Ty at level 0, x constr at level 0).
Notation "'Bool'" := TyBool (in custom IMPP_Ty at level 0).
Notation "'Int'" := TyInt (in custom IMPP_Ty at level 0).
Notation "'Float'" := TyFloat (in custom IMPP_Ty at level 0).
Notation "'Char'" := TyChar (in custom IMPP_Ty at level 0).
Notation "'String'" := TyString (in custom IMPP_Ty at level 0).
Notation "'Object'" := (TyClass "Object") (in custom IMPP_Ty at level 0).
Notation "T1 '->' T2" := (TyArrow T1 T2) (in custom IMPP_Ty at level 10,T2 at level 10).
Notation "'[]'" := TyVoid (in custom IMPP_Ty at level 0).
Notation "[ T ]" := (TyConcat T TyVoid) (in custom IMPP_Ty at level 0).
Notation "[ T1 ; T2 ; .. ; Tn ]" := (TyConcat T1 (TyConcat T2 .. (TyConcat Tn TyVoid)..)) (in custom IMPP_Ty at level 0).
Notation "T '[]'" := (TyArray T) (in custom IMPP_Ty at level 10).
Notation "x |--> y ; m" := (StrMap.add x y m) (at level 100, right associativity).
(* reserved class names *)
Open Scope string_scope.
Definition empty_map : StrMap.t Ty := StrMap.empty Ty.
Definition CMath : ClassType := (
    "max" |--> <([Int; Int] -> Int)>;
    "min" |--> <([Int; Int] -> Int)>;
    "PI" |--> <(Float)>;
    "E" |--> <(Float)>;
    "abs" |--> <([Int] -> Int)>;
    "sqrt" |--> <([Float] -> Float)>;
    "pow" |--> <([Float; Float] -> Float)>;
    "exp" |--> <([Float] -> Float)>;
    "log" |--> <([Float] -> Float)>;
    "log10" |--> <([Float] -> Float)>;
    "ceil" |--> <([Float] -> Float)>;
    "floor" |--> <([Float] -> Float)>;
    "round" |--> <([Float] -> Int)>;
    "tan" |--> <([Float] -> Float)>;
    empty_map
).
Definition CArrays : ClassType := (
    "asList" |--> <([Object[]] -> (TyGeneric1 "List" <(Object)>) )>;
    "equals" |--> <([Object[]; Object[]] -> Bool)>;
    "fill" |--> <([Object[];Object] -> [])>;
    "sort" |--> <([Object []] -> [])>;
    empty_map
).
Definition CInteger : ClassType := (
    "MAX_VALUE" |--> <(Int)>;
    "MIN_VALUE" |--> <(Int)>;
    "parseInt" |--> <([String] -> Int)>;
    "valueOf" |--> <([Object] -> Int)>;
    "toString" |--> <([Int] -> String)>;
    "toBinaryString" |--> <([Int] -> String)>;
    "equals" |--> <([Object] -> Bool)>;
    empty_map
).
Definition CString : ClassType := (
    "length" |--> <([] -> Int)>;
    "charAt" |--> <([Int] -> Char)>;
    "equals" |--> <([String] -> Bool)>;
    "indexOf" |--> <([String] -> Int)>;
    "lastIndexOf" |--> <([String] -> Int)>;
    "substring" |--> <([Int; Int] -> String)>;
    "replace" |--> <([Char; Char] -> String)>;
    "split" |--> <([Char] -> (TyGeneric1 "List" <(String)>) )>;
    "trim" |--> <([] -> String)>;
    "toLowerCase" |--> <([] -> String)>;
    "toUpperCase" |--> <([] -> String)>;
    "startsWith" |--> <([String] -> Bool)>;
    "endsWith" |--> <([String] -> Bool)>;
    "contains" |--> <([String] -> Bool)>;
    "isEmpty" |--> <([] -> Bool)>;
    "concat" |--> <([String] -> String)>;
    "valueOf" |--> <([Object] -> String)>;
    "toCharArray" |--> <([] -> Char[])>;
    "toString" |--> <([] -> String)>;
    empty_map
).
Definition CList(T:Ty) : ClassType := (
    "size" |--> <([] -> Int)>;
    "isEmpty" |--> <([] -> Bool)>;
    "contains" |--> <([T] -> Bool)>;
    "indexOf" |--> <([T] -> Int)>;
    "get" |--> <([Int] -> T)>;
    "set" |--> <([Int; T] -> T)>;
    "add" |--> <([T] -> [])>;
    "remove" |--> <([T] -> [])>;
    "clear" |--> <([] -> [])>;
    "toString" |--> <([] -> String)>;
    constructor |--> <([] -> [])>;
    empty_map
).
Definition CSet(T:Ty) : ClassType := (
    "size" |--> <([] -> Int)>;
    "isEmpty" |--> <([] -> Bool)>;
    "contains" |--> <([T] -> Bool)>;
    "add" |--> <([T] -> Bool)>;
    "remove" |--> <([T] -> [])>;
    "clear" |--> <([] -> [])>;
    "toString" |--> <([] -> String)>;
    constructor |--> <([] -> [])>;
    empty_map
).
Definition CMap(K V:Ty) : ClassType := (
    "size" |--> <([] -> Int)>;
    "isEmpty" |--> <([] -> Bool)>;
    "containsKey" |--> <([K] -> Bool)>;
    "containsValue" |--> <([V] -> Bool)>;
    "get" |--> <([K] -> V)>;
    "put" |--> <([K; V] -> [])>;
    "remove" |--> <([K] -> V)>;
    "clear" |--> <([] -> [])>;
    "keySet" |--> <([] -> (TyGeneric1 "Set" K))>;
    "values" |--> <([] -> (TyGeneric1 "List" V))>;
    "toString" |--> <([] -> String)>;
    constructor |--> <([] -> [])>;
    empty_map
).
Close Scope string_scope.
Definition empty_context : Context := {|
    var_type := empty_map;
    class_type := StrMap.empty ClassType
|}.

(* program definition *)
Inductive Term : Type :=
    (* basic data structure *)
    | TmVar : string->Term
    | TmInteger : nat->Term
    | TmFloat : float->Term
    | TmChar : nat->Term
    | TmString : string->Term
    | TmTrue : Term
    | TmFalse : Term
    | TmNull : Term
    (* advanced data structure *)
    | TmAssign : Term->Term->Term                   (* tm1 = tm2 *)
    | TmConversion : Ty->Term->Term                 (* (T)tm / (float)10 *)
    | TmInstanceOf : Term->Ty->Term                  (* tm instanceof T *)
    | TmChoose : Term->Term->Term->Term             (* tm1 ? tm2 : tm3 *)
    | TmFieldAccess : Term->string->Term            (* tm.f *)
    | TmArrayAccess : Term->Term->Term              (* tm1[tm2] *)
    | TmNew : Ty->Term->Term                        (* new T(tm) *)
    | TmNewArray0 : Ty->Term                        (* new T *)
    | TmNewArray1 : Term->Term->Term                (* new T[tm] / new int[2][2] *)
    | TmMethodInvocation : Term->string->Term->Term (* tm1.m(tm2) *)
    | TmMethodInvocationNoObj : string->Term->Term  (* m(tm) *)
    | TmType : Ty->Term                             (* T *)
    | TmList : list Term->Term                      (* [tm1,tm2,tm3] *)
    | TmArray : list Term->Term                     (* {tm1,tm2,tm3} *)
    | TmParenthesis : Term->Term                    (* (tm) *)
    (* arithmetic term *)
    | TmAdd : Term->Term->Term                      (* tm1 + tm2 *)
    | TmSub : Term->Term->Term                      (* tm1 - tm2 *)
    | TmMul : Term->Term->Term                      (* tm1 * tm2 *)
    | TmDiv : Term->Term->Term                      (* tm1 / tm2 *)
    | TmMod : Term->Term->Term                      (* tm1 % tm2 *)
    | TmNeg : Term->Term                            (* -tm *)
    | TmShiftL : Term->Term->Term                   (* tm1 << tm2 *)
    | TmShiftR : Term->Term->Term                   (* tm1 >> tm2 *)
    | TmBitAnd : Term->Term->Term                   (* tm1 & tm2 *)
    | TmBitOr : Term->Term->Term                    (* tm1 | tm2 *)
    | TmBitXor : Term->Term->Term                   (* tm1 ^ tm2 *)
    | TmBitNot : Term->Term                         (* ~tm *)
    | TmPostInc : Term->Term                        (* tm++ *)
    | TmPostDec : Term->Term                        (* tm-- *)
    | TmPreInc : Term->Term                         (* ++tm *)
    | TmPreDec : Term->Term                         (* --tm *)
    (*logic term*)
    | TmEq : Term->Term->Term                       (* tm1 == tm2 *)
    | TmNe : Term->Term->Term                       (* tm1 != tm2 *)
    | TmLt : Term->Term->Term                       (* tm1 < tm2 *)
    | TmLe : Term->Term->Term                       (* tm1 <= tm2 *)
    | TmGt : Term->Term->Term                       (* tm1 > tm2 *)
    | TmGe : Term->Term->Term                       (* tm1 >= tm2 *)
    | TmAnd : Term->Term->Term                      (* tm1 && tm2 *)
    | TmOr : Term->Term->Term                       (* tm1 || tm2 *)
    | TmNot : Term->Term                            (* !tm *).

Inductive Statement : Type :=
    | StSkip : Statement
    | StDeclInit : Ty->string->Term->Statement              (* T x = tm *)
    | StDeclNoInit : Ty->string->Statement                  (* T x *)
    | StIf : Term->Statement->Statement                     (* if (tm) {s} *)
    | StIfElse : Term->Statement->Statement->Statement      (* if (tm) {s1} else {s2} *)
    | StWhile : Term->Statement->Statement                  (* while (tm) {s} *)
    | StDoWhile : Statement->Term->Statement                (* do {s} while (tm) *)
    | StFor : Statement->Term->Term->Statement->Statement   (* for (s1;tm1;tm2) {s3} *)
    | StForeach : Ty->string->Term->Statement->Statement    (* for (T x : tm) {s} *)
    | StReturn : Term->Statement                            (* return tm *)
    | StContinue : Statement                                (* continue *)
    | StBreak : Statement                                   (* break *)
    | StExpression : Term->Statement                        (* tm *)
    | StConcat : Statement->Statement->Statement.

Inductive Program : Type :=
    | PgVarDeclNoInit :  string->Ty->string->Program                  (* modif T x; *)
    | PgVarDeclInit : string->Ty->string->Term->Program               (* modif T x = tm; *)
    | PgMethodDecl : string->Ty->string->Statement->Statement->Program(* modif T x(s1){s2} *)
    | PgConstructor : Statement->Statement->Program                   (* C (s1) {s2} *)
    | PgStatement : Statement->Program                                (* s *)
    | PgClassDecl : string->Program->Program                          (* class x {p} *)
    | PgConcat : Program->Program->Program.                           (* p1 p2 *)



(* helper functions *)
Definition findVarType (Gamma:Context)(x:string) : option Ty :=
    var_type Gamma !! x.
Definition findClassType (Gamma:Context)(t:Ty) : option ClassType :=
    match t with
    | TyString => Some CString
    | TyInt => Some CInteger
    | TyClass "Math" => Some CMath
    | TyClass "Arrays" => Some CArrays
    | TyClass "Integer" => Some CInteger
    | TyClass name =>  class_type Gamma !! name 
    | TyGeneric0 "List" => Some (CList TyVoid)
    | TyGeneric0 "Set" => Some (CSet TyVoid)
    | TyGeneric0 "Map" => Some (CMap TyVoid TyVoid)
    | TyGeneric1 "List" T => Some (CList T)
    | TyGeneric1 "Set" T => Some (CSet T)
    | TyGeneric2 "Map" K V => Some (CMap K V)
    | _ => None
    end.

(* check if a type t2 can be converted to t1 *)
Fixpoint convertible (ty1 ty2: Ty) : bool :=
    match ty1, ty2 with
    | TyInt, TyInt => true
    | TyFloat, TyFloat => true
    | TyBool, TyBool => true
    | TyChar, TyChar => true
    | TyString, TyString => true
    | TyInt, TyFloat => true
    | TyFloat, TyInt => true
    | TyInt, TyChar => true
    | TyChar, TyInt => true
    | TyInt, TyBool => true
    | TyBool, TyInt => true
    | TyClass "Object", _ => true
    | _, TyClass "Object" => true
    | TyClass m, TyClass n => String.eqb m n
    | TyGeneric1 m ty, TyGeneric0 n => String.eqb m n
    | TyGeneric1 m t1, TyGeneric1 n t2 => String.eqb m n && convertible t1 t2
    | TyGeneric2 m t1 t2, TyGeneric0 n => String.eqb m n
    | TyGeneric2 m t1 t2, TyGeneric2 n t3 t4 => String.eqb m n && convertible t1 t3 && convertible t2 t4
    | TyArray t1, TyArray t2 => convertible t1 t2
    | TyVoid, TyVoid => true
    | TyConcat t1 l1, TyConcat t2 l2 => convertible t1 t2 && convertible l1 l2
    | _, _ => false
    end.

(* check if type t2 is a collection of t1*)
Definition iterable (ty1 ty2: Ty) : bool :=
    match ty1, ty2 with
    | t , TyArray t' => convertible t t'
    | t , TyGeneric1 _ t' => convertible t t'
    | t , TyGeneric2 _ t' _ => convertible t t'
    | _, _ => false
    end.
Definition binary_term_type (tm: Term)(ty1 ty2 : Ty): option Ty :=
    match tm with
    | TmAdd _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyInt, TyFloat => Some TyFloat
                    | TyFloat, TyInt => Some TyFloat
                    | TyFloat, TyFloat => Some TyFloat
                    | TyString, TyString => Some TyString
                    | _, _ => None
                    end
    | TmSub _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyInt, TyFloat => Some TyFloat
                    | TyFloat, TyInt => Some TyFloat
                    | TyFloat, TyFloat => Some TyFloat
                    | _, _ => None
                    end
    | TmMul _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyInt, TyFloat => Some TyFloat
                    | TyFloat, TyInt => Some TyFloat
                    | TyFloat, TyFloat => Some TyFloat
                    | _, _ => None
                    end
    | TmDiv _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyInt, TyFloat => Some TyFloat
                    | TyFloat, TyInt => Some TyFloat
                    | TyFloat, TyFloat => Some TyFloat
                    | _, _ => None
                    end
    | TmMod _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | _, _ => None
                    end
    | TmBitAnd _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyBool, TyBool => Some TyBool
                    | _, _ => None
                    end
    | TmBitOr _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyBool, TyBool => Some TyBool
                    | _, _ => None
                    end
    | TmBitXor _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyInt
                    | TyBool, TyBool => Some TyBool
                    | _, _ => None
                    end
    | TmEq _ _ => if convertible ty1 ty2 then Some TyBool else None
    | TmNe _ _ => if convertible ty1 ty2 then Some TyBool else None
    | TmLt _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyBool
                    | TyInt, TyFloat => Some TyBool
                    | TyFloat, TyInt => Some TyBool
                    | TyFloat, TyFloat => Some TyBool
                    | TyChar, TyChar => Some TyBool
                    | TyChar, TyInt => Some TyBool
                    | TyInt, TyChar => Some TyBool
                    | _, _ => None
                    end
    | TmLe _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyBool
                    | TyInt, TyFloat => Some TyBool
                    | TyFloat, TyInt => Some TyBool
                    | TyFloat, TyFloat => Some TyBool
                    | TyChar, TyChar => Some TyBool
                    | TyChar, TyInt => Some TyBool
                    | TyInt, TyChar => Some TyBool
                    | _, _ => None
                    end
    | TmGt _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyBool
                    | TyInt, TyFloat => Some TyBool
                    | TyFloat, TyInt => Some TyBool
                    | TyFloat, TyFloat => Some TyBool
                    | TyChar, TyChar => Some TyBool
                    | TyChar, TyInt => Some TyBool
                    | TyInt, TyChar => Some TyBool
                    | _, _ => None
                    end
    | TmGe _ _ => match ty1, ty2 with
                    | TyInt, TyInt => Some TyBool
                    | TyInt, TyFloat => Some TyBool
                    | TyFloat, TyInt => Some TyBool
                    | TyFloat, TyFloat => Some TyBool
                    | TyChar, TyChar => Some TyBool
                    | TyChar, TyInt => Some TyBool
                    | TyInt, TyChar => Some TyBool
                    | _, _ => None
                    end
    | _ => None
    end.
Definition unary_term_type (tm: Term)(ty: Ty): option Ty :=
    match tm with
    | TmNeg _ => match ty with
                    | TyInt => Some TyInt
                    | TyFloat => Some TyFloat
                    | _ => None
                    end
    | TmBitNot _ => match ty with
                    | TyInt => Some TyInt
                    | TyBool => Some TyBool
                    | _ => None
                    end
    | TmPostInc _ => match ty with
                    | TyInt => Some TyInt
                    | TyFloat => Some TyFloat
                    | _ => None
                    end
    | TmPostDec _ => match ty with
                    | TyInt => Some TyInt
                    | TyFloat => Some TyFloat
                    | _ => None
                    end
    | TmPreInc _ => match ty with
                    | TyInt => Some TyInt
                    | TyFloat => Some TyFloat
                    | _ => None
                    end
    | TmPreDec _ => match ty with
                    | TyInt => Some TyInt
                    | TyFloat => Some TyFloat
                    | _ => None
                    end
    | _ => None
    end.


(*extract all the declaration types in the formal arguments*)
Fixpoint DeclsInStatement (s:Statement) : Ty :=
    match s with
    | StDeclInit T x t => T
    | StDeclNoInit T x => T 
    | StConcat s1 s2 => match DeclsInStatement s1 , DeclsInStatement s2 with
                        | TyVoid, t => t
                        | t, TyVoid => t
                        | t1, t2 => TyConcat t1 t2
                        end
    | _ => TyVoid
    end.

Fixpoint DeclsInStatement' (s:Statement) : ClassType :=
    match s with
    | StDeclInit T x t => StrMap.add x T empty_map
    | StDeclNoInit T x => StrMap.add x T empty_map
    | StConcat s1 s2 => let s1 := DeclsInStatement' s1 in
                        let s2 := DeclsInStatement' s2 in
                        StrMap.fold (fun x T acc => StrMap.add x T acc) s1 s2
    | _ => empty_map
    end.

(*extract all the declarations in the class definition*)
Fixpoint DeclsInClassDefinition (p: Program) : ClassType :=
    match p with
    | PgVarDeclNoInit _ T x => StrMap.add x T empty_map
    | PgVarDeclInit _ T x tm => StrMap.add x T empty_map
    | PgConstructor s1 s2 => StrMap.add constructor (TyArrow (DeclsInStatement s1) TyVoid) empty_map
    | PgMethodDecl _ T x s1 s2 => StrMap.add x (TyArrow (DeclsInStatement s1) T) empty_map
    | PgStatement s => DeclsInStatement' s
    | PgConcat p1 p2 => let p1 := DeclsInClassDefinition p1 in
                        let p2 := DeclsInClassDefinition p2 in
                        StrMap.fold (fun x T acc => StrMap.add x T acc) p1 p2
    | PgClassDecl _ p => DeclsInClassDefinition p
    end.

(*typing rules for terms*)
Reserved Notation "Gamma '|--' t '\in' T" (at level 100, T at level 0).
Inductive has_type : Context->Term->Ty->Prop :=
    (*basic data structure*)
    | T_Var : forall Gamma x T,
        findVarType Gamma x = Some T ->
        Gamma |-- (TmVar x) \in T
    | T_Integer : forall Gamma n,
        Gamma |-- (TmInteger n) \in TyInt
    | T_Float : forall Gamma f,
        Gamma |-- (TmFloat f) \in TyFloat
    | T_Char : forall Gamma c,
        Gamma |-- (TmChar c) \in TyChar
    | T_String : forall Gamma s,
        Gamma |--  (TmString s) \in TyString
    | T_True : forall Gamma,
        Gamma |-- TmTrue \in TyBool
    | T_False : forall Gamma,
        Gamma |-- TmFalse \in TyBool
    | T_Null : forall Gamma T,
        Gamma |-- TmNull \in T (*null can have any type*)
    (*advanced data structure*)
    | T_Assign : forall Gamma x T t,
        (* x = t *)
        Gamma |-- x \in T ->
        Gamma |-- t \in T ->
        Gamma |-- (TmAssign x t) \in T
    | T_Conversion : forall Gamma T t T', 
        (* (T)t *)
        Gamma |-- t \in T' ->
        convertible T T' = true ->
        Gamma |-- (TmConversion T t) \in T
    | T_InstanceOf : forall Gamma tm T,
        (* tm instanceof T *)
        Gamma |-- (TmInstanceOf tm T) \in TyBool
    | T_Choose : forall Gamma tm1 tm2 tm3 T,
        (* tm1 ? tm2 : tm3 *)
        Gamma |-- tm1 \in TyBool ->
        Gamma |-- tm2 \in T ->
        Gamma |-- tm3 \in T ->
        Gamma |-- (TmChoose tm1 tm2 tm3) \in T
    | T_FieldAccess : forall Gamma tm f CT T T',
        (* tm.f *)
        Gamma |-- tm \in T' ->
        findClassType Gamma T' = Some CT ->
        CT !! f = Some T ->
        Gamma |-- TmFieldAccess tm f \in T
    | T_ArrayAccess : forall Gamma tm1 tm2 T, 
        (* tm1[tm2] *)
        Gamma |-- tm1 \in ( TyArray T ) ->
        Gamma |-- tm2 \in TyInt ->
        Gamma |-- TmArrayAccess tm1 tm2 \in T
    | T_New : forall Gamma T param PT PT' CT,
        (* new T(param) *)
        findClassType Gamma T = Some CT ->
        CT !! constructor = Some (TyArrow PT TyVoid) ->
        Gamma |-- param \in PT' ->
        convertible PT PT' = true ->
        Gamma |-- TmNew T param \in T
    | T_NewArray0 : forall Gamma T,
        (* new T *)
        Gamma |-- TmNewArray0 T \in T
    | T_NewArray1 : forall Gamma T tm1 tm2,
        (* new T[tm2] *)
        Gamma |-- tm2 \in TyInt ->
        Gamma |-- tm1 \in T ->
        Gamma |-- TmNewArray1 tm1 tm2 \in (TyArray T)
    | T_MethodInvocation : forall Gamma tm m param CT PT PT' RT T,
        (* tm.m(param) *)
        Gamma |-- tm \in T ->
        findClassType Gamma T = Some CT ->
        CT !! m = Some ( TyArrow PT RT ) ->
        Gamma |-- param \in PT' ->
        convertible PT PT' = true ->
        Gamma |-- TmMethodInvocation tm m param \in RT
    | T_MethodInvocationNoObj : forall Gamma m param PT PT' RT,
        (* m(param) *)
        findVarType Gamma m = Some (TyArrow PT RT) ->
        Gamma |-- param \in PT' ->
        convertible PT PT' = true ->
        Gamma |-- TmMethodInvocationNoObj m param \in RT
    | T_Type : forall Gamma T,
        (* T *)
        Gamma |-- (TmType T) \in T
    | T_List0 : forall Gamma,
        (* empty list *)
        Gamma |-- TmList nil \in TyVoid
    | T_List1 : forall Gamma tm1 tm2 T1 T2,
        (* tm1,tm2... *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- TmList tm2 \in T2 ->
        Gamma |-- (TmList (tm1::tm2)) \in (TyConcat T1 T2)
    | T_Array0: forall Gamma T,
        (* empty array *)
        Gamma |-- TmArray nil \in (TyArray T)
    | T_Array1: forall Gamma tm1 tm2 T,
        (* {tm1,tm2...} *)
        Gamma |-- tm1 \in T ->
        Gamma |-- TmArray tm2 \in (TyArray T) ->
        Gamma |-- (TmArray (tm1::tm2)) \in (TyArray T)
    | T_Parenthesis : forall Gamma tm T,
        (* (tm) *)
        Gamma |-- tm \in T ->
        Gamma |-- (TmParenthesis tm) \in T
    (*arithmetic term*)
    | T_Add : forall Gamma tm1 tm2 Ty1 Ty2 Ty3,
        (* tm1 + tm2 *)
        Gamma |-- tm1 \in Ty1 ->
        Gamma |-- tm2 \in Ty2 ->
        binary_term_type (TmAdd tm1 tm2) Ty1 Ty2 = Some Ty3 ->
        Gamma |-- (TmAdd tm1 tm2) \in Ty3
    | T_Sub : forall Gamma tm1 tm2 Ty1 Ty2 Ty3,
        (* tm1 - tm2 *)
        Gamma |-- tm1 \in Ty1 ->
        Gamma |-- tm2 \in Ty2 ->
        binary_term_type (TmSub tm1 tm2) Ty1 Ty2 = Some Ty3 ->
        Gamma |-- (TmSub tm1 tm2) \in Ty3
    | T_Mul : forall Gamma tm1 tm2 Ty1 Ty2 Ty3,
        (* tm1 * tm2 *)
        Gamma |-- tm1 \in Ty1 ->
        Gamma |-- tm2 \in Ty2 ->
        binary_term_type (TmMul tm1 tm2) Ty1 Ty2 = Some Ty3 ->
        Gamma |-- (TmMul tm1 tm2) \in Ty3
    | T_Div : forall Gamma tm1 tm2 Ty1 Ty2 Ty3,
        (* tm1 / tm2 *)
        Gamma |-- tm1 \in Ty1 ->
        Gamma |-- tm2 \in Ty2 ->
        binary_term_type (TmDiv tm1 tm2) Ty1 Ty2 = Some Ty3 ->
        Gamma |-- (TmDiv tm1 tm2) \in Ty3
    | T_Mod : forall Gamma tm1 tm2 Ty1 Ty2 Ty3,
        (* tm1 % tm2 *)
        Gamma |-- tm1 \in Ty1 ->
        Gamma |-- tm2 \in Ty2 ->
        binary_term_type (TmMod tm1 tm2) Ty1 Ty2 = Some Ty3 ->
        Gamma |-- (TmMod tm1 tm2) \in Ty3
    | T_Neg : forall Gamma tm Ty1 Ty2,
        (* -tm *)
        Gamma |-- tm \in Ty1 ->
        unary_term_type (TmNeg tm) Ty1 = Some Ty2 ->
        Gamma |-- (TmNeg tm) \in Ty2
    | T_ShiftL : forall Gamma tm1 tm2,
        (* tm1 << tm2 *)
        Gamma |-- tm1 \in TyInt ->
        Gamma |-- tm2 \in TyInt ->
        Gamma |-- (TmShiftL tm1 tm2) \in TyInt
    | T_ShiftR : forall Gamma tm1 tm2,
        (* tm1 >> tm2 *)
        Gamma |-- tm1 \in TyInt ->
        Gamma |-- tm2 \in TyInt ->
        Gamma |-- (TmShiftR tm1 tm2) \in TyInt
    | T_BitAnd : forall Gamma tm1 tm2 T1 T2 T3,
        (* tm1 & tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmBitAnd tm1 tm2) T1 T2 = Some T3 ->
        Gamma |-- (TmBitAnd tm1 tm2) \in T3
    | T_BitOr : forall Gamma tm1 tm2 T1 T2 T3,
        (* tm1 | tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmBitOr tm1 tm2) T1 T2 = Some T3 ->
        Gamma |-- (TmBitOr tm1 tm2) \in T3
    | T_BitXor : forall Gamma tm1 tm2 T1 T2 T3,
        (* tm1 ^ tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmBitXor tm1 tm2) T1 T2 = Some T3 ->
        Gamma |-- (TmBitXor tm1 tm2) \in T3
    | T_BitNot : forall Gamma tm T1 T2,
        (* ~tm *)
        Gamma |-- tm \in T1 ->
        unary_term_type (TmBitNot tm) T1 = Some T2 ->
        Gamma |-- (TmBitNot tm) \in T2
    | T_PostInc : forall Gamma tm T1 T2,
        (* tm++ *)
        Gamma |-- tm \in T1 ->
        unary_term_type (TmPostInc tm) T1 = Some T2 ->
        Gamma |-- (TmPostInc tm) \in T2
    | T_PostDec : forall Gamma tm T1 T2,
        (* tm-- *)
        Gamma |-- tm \in T1 ->
        unary_term_type (TmPostDec tm) T1 = Some T2 ->
        Gamma |-- (TmPostDec tm) \in T2
    | T_PreInc : forall Gamma tm T1 T2,
        (* ++tm *)
        Gamma |-- tm \in T1 ->
        unary_term_type (TmPreInc tm) T1 = Some T2 ->
        Gamma |-- (TmPreInc tm) \in T2
    | T_PreDec : forall Gamma tm T1 T2,
        (* --tm *)
        Gamma |-- tm \in T1 ->
        unary_term_type (TmPreDec tm) T1 = Some T2 ->
        Gamma |-- (TmPreDec tm) \in T2
    (*logic term*)
    | T_Eq : forall Gamma tm1 tm2 T1 T2,
        (* tm1 == tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmEq tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmEq tm1 tm2) \in TyBool
    | T_Ne : forall Gamma tm1 tm2 T1 T2,
        (* tm1 != tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmNe tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmNe tm1 tm2) \in TyBool
    | T_Lt : forall Gamma tm1 tm2 T1 T2,
        (* tm1 < tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmLt tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmLt tm1 tm2) \in TyBool
    | T_Le : forall Gamma tm1 tm2 T1 T2,
        (* tm1 <= tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmLe tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmLe tm1 tm2) \in TyBool
    | T_Gt : forall Gamma tm1 tm2 T1 T2,
        (* tm1 > tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmGt tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmGt tm1 tm2) \in TyBool
    | T_Ge : forall Gamma tm1 tm2 T1 T2,
        (* tm1 >= tm2 *)
        Gamma |-- tm1 \in T1 ->
        Gamma |-- tm2 \in T2 ->
        binary_term_type (TmGe tm1 tm2) T1 T2 = Some TyBool ->
        Gamma |-- (TmGe tm1 tm2) \in TyBool
    | T_And : forall Gamma tm1 tm2,
        (* tm1 && tm2 *)
        Gamma |-- tm1 \in TyBool ->
        Gamma |-- tm2 \in TyBool ->
        Gamma |-- (TmAnd tm1 tm2) \in TyBool
    | T_Or : forall Gamma tm1 tm2,
        (* tm1 || tm2 *)
        Gamma |-- tm1 \in TyBool ->
        Gamma |-- tm2 \in TyBool ->
        Gamma |-- (TmOr tm1 tm2) \in TyBool
    | T_Not : forall Gamma tm,
        (* !tm *)
        Gamma |-- tm \in TyBool ->
        Gamma |-- (TmNot tm) \in TyBool
where "Gamma '|--' t '\in' T" := (has_type Gamma t T).

(*typing rules for statements*)
Reserved Notation "Gamma1 '--' s '-->' Gamma2" (at level 100, Gamma2 at level 0).
Inductive well_type_statement : Context->Statement->Context->Prop :=
    | T_Skip : forall Gamma,
        Gamma -- StSkip --> Gamma
    | T_DeclInit : forall Gamma x tm T T',
        (* T x = tm *)
        Gamma |-- tm \in T' ->
        convertible T T' = true ->
        Gamma -- (StDeclInit T x tm) --> (x|->T;Gamma)
    | T_DeclNoInit : forall Gamma x T,
        (* T x *)
        Gamma -- (StDeclNoInit T x) --> (x|->T;Gamma)
    | T_If : forall Gamma1 tm s Gamma2,
        (* if (tm) {s} *)
        Gamma1 |-- tm \in TyBool ->
        Gamma1 -- s --> Gamma2 ->
        Gamma1 -- StIf tm s --> Gamma1
        (*changes in s don't take effect outside*)
    | T_IfElse : forall Gamma1 tm s1 s2 Gamma2 Gamma3,
        (* if (tm) {s1} else {s2} *)
        Gamma1 |-- tm \in TyBool ->
        Gamma1 -- s1 --> Gamma2 ->
        Gamma1 -- s2 --> Gamma3 ->
        Gamma1 -- StIfElse tm s1 s2 --> Gamma1
        (*changes in s1 and s2 don't take effect outside*)
    | T_While : forall Gamma1 tm s Gamma2,
        (* while (tm) {s} *)
        Gamma1 |-- tm \in TyBool ->
        Gamma1 -- s --> Gamma2 ->
        Gamma1 -- StWhile tm s --> Gamma1
        (*changes in s don't take effect outside*)
    | T_DoWhile : forall Gamma1 s tm Gamma2,
        (* do {s} while (tm) *)
        Gamma1 -- s --> Gamma2 ->
        Gamma2 |-- tm \in TyBool ->
        Gamma1 -- (StDoWhile s tm) --> Gamma1
    | T_For : forall Gamma1 s1 s2 tm1 tm2 T Gamma2 Gamma3,
        (* for (s1;tm1;tm2) {s2} *)
        Gamma1 -- s1 --> Gamma2 ->
        Gamma2 |-- tm1 \in TyBool ->
        Gamma2 |-- tm2 \in T ->
        Gamma2 -- s2 --> Gamma3 ->
        Gamma1 -- StFor s1 tm1 tm2 s2 --> Gamma1
    | T_Foreach : forall Gamma1 x T T' tm s Gamma2,
        (* for (T x : tm) {s} *)
        Gamma1 |-- tm \in T' ->
        iterable T T' = true ->
        (x|->T;Gamma1) -- s --> Gamma2 ->
        Gamma1 -- (StForeach T x tm s) --> Gamma1
    | T_Return : forall Gamma tm T T',
        Gamma |-- tm \in T' ->
        findVarType Gamma return' = Some T ->
        convertible T T' = true ->
        Gamma -- StReturn tm --> Gamma
    | T_Continue : forall Gamma,
        Gamma -- StContinue--> Gamma
    | T_Break : forall Gamma,
        Gamma -- StBreak --> Gamma
    | T_Expression : forall Gamma tm T,
        Gamma |-- tm \in T ->
        Gamma -- StExpression tm --> Gamma
    | T_Concat : forall Gamma1 s1 Gamma2 s2 Gamma3,
        Gamma1 -- s1 --> Gamma2 ->
        Gamma2 -- s2 --> Gamma3 ->
        Gamma1 -- (StConcat s1 s2) --> Gamma3
where "Gamma1 '--' s '-->' Gamma2" := (well_type_statement Gamma1 s Gamma2).

(*typing rules for class_components*)
Reserved Notation "Gamma1 '|-' c '-->' Gamma2" (at level 100, Gamma2 at level 0).
Inductive well_type_program : Context->Program->Context->Prop :=
    | T_FieldDeclNoInit : forall Gamma T x modif,  
        (* modifier T x; *)
        Gamma |- (PgVarDeclNoInit modif T x) --> (x|->T;Gamma)
    | T_FieldDeclInit : forall Gamma T T' x modif tm,
        (* modifier T x = tm; *)
        Gamma |-- tm \in T' ->
        convertible T T' = true ->
        Gamma |- (PgVarDeclInit modif T x tm) --> (x|->T;Gamma)
    | T_ConstructorDecl : forall Gamma1 Gamma2 s1 s2 T,
        (* Constructor (s1) {s2} *)
        Gamma1 -- s1 --> Gamma2 ->
        DeclsInStatement s1 = T ->
        Gamma2 -- s2 --> Gamma2 ->
        Gamma1 |- (PgConstructor s1 s2) --> (constructor|->(TyArrow T TyVoid);Gamma1)
    | T_MethodDecl : forall Gamma1 Gamma2 Gamma3 T PT param s modif m,
        (* modifier T m (param) {s} *)
        Gamma1 -- param --> Gamma2 ->
        DeclsInStatement param = PT ->
        (m|->(TyArrow PT T);(return'|->T;Gamma2)) -- s --> Gamma3 -> (*recursion*)
        Gamma1 |- (PgMethodDecl modif T m param s) --> (m|->(TyArrow PT T);Gamma1)
    | T_Statement : forall Gamma1 Gamma2 s,
        (* s *)
        Gamma1 -- s --> Gamma2 ->
        Gamma1 |- (PgStatement s) --> Gamma2
    | T_ClassDecl : forall Gamma1 Gamma2 name p CT,
        (* class name {p} *)
        Gamma1 |- p --> Gamma2 ->
        DeclsInClassDefinition p = CT ->
        Gamma1 |- (PgClassDecl name p) --> {|
            var_type := Gamma1.(var_type);
            class_type := StrMap.add name CT Gamma1.(class_type)
        |}
    | T_ProgramConcat : forall Gamma1 Gamma2 Gamma3 c1 c2,
        Gamma1 |- c1 --> Gamma2 ->
        Gamma2 |- c2 --> Gamma3 ->
        Gamma1 |- (PgConcat c1 c2) --> Gamma3
where "Gamma1 '|-' c '-->' Gamma2" := (well_type_program Gamma1 c Gamma2).

Definition program_well_typed (p:Program) : Prop := 
    exists Gamma, empty_context |- p --> Gamma.

(*ltac to extract the well-typed program*)
Ltac get_the_exists_term_tac H :=
  match H with
  | @ex_intro _ _ ?x _ =>
      constr:(x)
  end.
Notation "'the_exists_term' H" :=
  ltac:(
    first 
    [ is_const H;
      let H0 := eval hnf in H in
      let x := get_the_exists_term_tac H0 in
      exact x
    | let x := get_the_exists_term_tac H in
      exact x
    ])
  (at level 1, H at level 0).
