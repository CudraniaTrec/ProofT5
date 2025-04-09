## IMPPlus 语言的语法

### 类型
```ebnf
S ::= String
Ty ::= 
    | Int 
    | Float 
    | Bool 
    | Char 
    | String 
    | [Ty]              (* Array *)
    | S<Ty>             (* Genereic1 *)
    | S<Ty,Ty>          (* Generic2 *)
    | Ty -> Ty          (* Function *)
    | class S           (* User defined class *)
    | Ty,Ty,...,Ty      (* List of types *)
```

### 表达式
```ebnf
Term ::= 
    (* Basic terms *)
    | String            (* Variable *)
    | Ints              (* Integer *)
    | Floats            (* Float *)
    | Chars             (* Char *)
    | String            (* String *)
    | true              (* True *)
    | false             (* False *)
    | null              (* Null *)
    (* Advanced terms *)
    | tm = tm           (* Assign *)
    | (T)tm             (* Conversion *)
    | tm ? tm : tm      (* Choose *)
    | tm.f              (* FieldAccess *)
    | tm[tm]            (* ArrayAccess *)
    | new T(tm)         (* New Object *)
    | new T[tm]         (* New Array *)
    | tm.m(tm)          (* MethodInvocation *)
    | m(tm)             (* Direct MethodInvocation *)
    | tm,tm,...,tm      (* List of Terms *)
    | {tm,tm,...,tm}    (* Array *)
    (* Arithmetic terms *)
    | tm + tm           (* Add *)
    | tm - tm           (* Sub *)
    | tm * tm           (* Mul *)
    | tm / tm           (* Div *)
    | tm % tm           (* Mod *)
    | -tm               (* Neg *)
    | tm << tm          (* ShiftL *)
    | tm >> tm          (* ShiftR *)
    | tm & tm           (* BitAnd *)
    | tm | tm           (* BitOr *)
    | tm ^ tm           (* BitXor *)
    | ~tm               (* BitNot *)
    | tm++              (* PostInc *)
    | tm--              (* PostDec *)
    | ++tm              (* PreInc *)
    | --tm              (* PreDec *)
    (* Logic terms *)
    | tm == tm          (* Eq *)
    | tm != tm          (* Ne *)
    | tm < tm           (* Lt *)
    | tm <= tm          (* Le *)
    | tm > tm           (* Gt *)
    | tm >= tm          (* Ge *)
    | tm && tm          (* And *)
    | tm || tm          (* Or *)
    | !tm               (* Not *)
```

### 语句
```ebnf
Statement ::= 
    | skip                             (* Skip *)
    | Ty x = tm                        (* Var Decl No Init Value *)
    | Ty x                             (* Var Decl with Init Value *)
    | if (tm) {s}                      (* If *)
    | if (tm) {s1} else {s2}           (* IfElse *)
    | while (tm) {s}                   (* While *)
    | do {s} while (tm)                (* DoWhile *)
    | for (s1;tm1;tm2) {s3}            (* For *)
    | for (Ty x : tm) {s}              (* Foreach *)
    | return tm                        (* Return *)
    | continue                         (* Continue *)
    | break                            (* Break *)
    | Term                             (* Expression *)
    | switch (tm) {case tm1: s1; case tm2: s2; default: s3;} (* Switch *)
    | s; s                             (* Concat *)
```

### 程序
```ebnf
Program ::= 
    | modifier Ty x;                  (* Var Decl No Init Value *)
    | modifier Ty x = tm;             (* Var Decl with Init Value *)
    | modifier Ty x(s1){s2}           (* Method Declaration *)
    | C (s1) {s2}                     (* Constructor Declaration *)
    | s                               (* Statement *)
    | class x {p}                     (* Class Declaration *)
    | p p                             (* Concat *)
```