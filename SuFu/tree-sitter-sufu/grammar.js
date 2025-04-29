/**
 * @file Sufu grammar for tree-sitter
 * @author hzc
 * @license MIT
 */
// <program> := <command> ... <command>
// <command> := Inductive <Name> = <name> <type> | ... | <name> <type>;     
//                                                                /* Define inductive data types */
//           |  <Name> = <type>;                                  /* Define type abbrevations */  
//           |  <name> = <term>;                                  /* Define functions or constants */
// <type>    := {<type>, ..., <type>}                             /* Product types */
//           |  <type> -> <type>                                  /* Arrow types */
//           |  Reframe <type>                                    /* Annotated types */
//           |  Unit | Int | Bool | <Name>                        /* Basic types or defined inductive types */
// <term>    := unit | <integer> | true | false | <name>          /* Basic values or variables*/
//           |  + | - | * | / | < | <= | > | >= | == | and | or | not       
//                                                                /* Builtin operators */
//           |  <term> <term>                                     /* Function applications */
//           |  \<name>:<type>. <term>                            /* Lambda expressions */
//           |  fix <term>                                        /* Recursions defined using the fix point */
//           |  let <name> = <term> in <term>                     /* Let bindings */
//           |  if <term> then <term> else <term>                 /* Branch expressions */
//           |  {<term>, ..., <term>}                             /* Tuple constructors */
//           |  <term>.<integer>                                  /* Tuple projections */
//           |  match <term> with <pattern> -> <term> | ... | <pattern> -> <term> end 
//                                                                /* Pattern matching */
//           |  rewrite <term> | label <term> | unlabel <term>    /* Annotated terms */
// <pattern> := _ | <name>                                        /* Matching without conditions */
//           |  <name> <pattern>                                  /* Matching constructors */
//           |  {<pattern>, ..., <pattern>}                       /* Matching for tuples*/
const PREC = {
  "TERM_APP": 0,
  "TERM_LAMBDA": -2,
  "TERM_FIX": 0,
  "TERM_LET": -4,
  "TERM_IF": -3,
  "TERM_MATCH": 5,
  "TERM_PROJECTION": 7,
  "TERM_REWRITTEN": -1,
  "TERM_LABEL": -1,
  "TERM_UNLABEL": -1,
  "PAREN": 10,
  "TYPE_REFRAME": 1,
  "TYPE_ARROW": 0,
}
module.exports = grammar({
  name: "sufu",

  supertypes: $ => [
    $.command,
    $.typedef,
    $.type,
    $.term,
    $.pattern,
  ],

  extras: $ => [
    /\s/,
  ],

  word: $ => $.identifier,

  conflicts: $ => [
  ],

  rules: {
    source_file: $ => repeat1($.command),

    command: $ => choice(
      $.inductive_command,
      $.definition_command,
      $.type_abbreviation_command,
    ),

    inductive_command: $ => seq(
      'Inductive',
      $.Identifier,
      '=',
      $.typedef,
      ';'
    ),

    typedef: $ => choice(
      $.typedef_single,
      $.typedef_cons,
    ),

    typedef_single: $ => seq(
      $.identifier,
      $.type,
    ),

    typedef_cons: $ => seq(
      $.typedef_single,
      repeat1(seq(
        '|',
        $.typedef_single,
    ))),

    definition_command: $ => seq(
      $.identifier,
      '=',
      $.term,
      ';',
    ),

    type_abbreviation_command: $ => seq(
      $.Identifier,
      '=',
      $.type,
      ';',
    ),

    type: $ => choice(
      $.type_product,
      $.type_arrow,
      $.type_reframe,
      $.type_inductive,
      $.type_int,
      $.type_bool,
      $.type_unit,
      $.type_parenthesized,
    ),

    type_product: $ => seq(
      '{',
      $.type,
      repeat1(seq(',', $.type)),
      '}',
    ),

    type_arrow: $ => prec.right(PREC.TYPE_ARROW, seq(
      $.type,
      '->',
      $.type,
    )),

    type_reframe: $ => prec(PREC.TYPE_REFRAME, seq(
      choice('Reframe', 'Compress'),
      $.type,
    )),

    type_inductive: $ => seq(
      $.Identifier,
    ),

    type_int: $ => 'Int',

    type_bool: $ => 'Bool',

    type_unit: $ => 'Unit',

    type_parenthesized: $ => prec(PREC.PAREN, seq(
      '(',
      $.type,
      ')',
    )),

    term: $ => choice(
      $.term_unit,
      $.term_integer,
      $.term_bool,
      $.term_var,
      $.term_app,
      $.term_lambda,
      $.term_fix,
      $.term_let,
      $.term_if,
      $.term_tuple,
      $.term_proj,
      $.term_match,
      $.term_rewrite,
      $.term_label,
      $.term_unlabel,
      $.term_op,
      $.term_parenthesized,
    ),

    term_unit: $ => 'unit',
    term_integer: $ => /[-+]?\d+/,
    term_bool: $ => choice('true', 'false'),
    term_var: $ => $.identifier,
    term_app: $ => prec.left(PREC.TERM_APP, seq(
      $.term,
      $.term,
    )),

    term_lambda: $ => prec(PREC.TERM_LAMBDA, seq(
      '\\',
      $.identifier,
      ':',
      $.type,
      '.',
      $.term,
    )),

    term_fix: $ => prec(PREC.TERM_FIX, seq(
      'fix',
      $.term_parenthesized,
    )),

    term_let: $ => prec(PREC.TERM_LET, seq(
      'let',
      $.identifier,
      '=',
      $.term,
      'in',
      $.term,
    )),

    term_if: $ => prec(PREC.TERM_IF, seq(
      'if',
      $.term,
      'then',
      $.term,
      'else',
      $.term,
    )),

    term_tuple: $ => seq(
      '{',
      $.term,
      repeat1(seq(',', $.term)),
      '}',
    ),

    term_proj: $ => prec(PREC.TERM_PROJECTION, seq(
      $.term,
      '.',
      $.term_integer,
    )),

    term_match: $ => prec(PREC.TERM_MATCH, seq(
      'match',
      $.term,
      'with',
      $.match_case,
    )),

    match_case: $ => seq(
      $.match_case_single,
      repeat(seq(
        '|',
        $.match_case_single,
      )),
      'end',
    ),

    match_case_single: $ => seq(
      $.pattern,
      '->',
      $.term,
    ),

    term_rewrite: $ => prec(PREC.TERM_REWRITTEN, seq(
      choice('rewrite', 'align'),
      $.term,
    )),

    term_label: $ => prec(PREC.TERM_LABEL, seq(
      'label',
      $.term,
    )),

    term_unlabel: $ => prec(PREC.TERM_UNLABEL,seq(
      'unlabel',
      $.term,
    )),

    term_op: $ => choice(
      '+',
      '-',
      '*',
      '/',
      '<',
      '<=',
      '>',
      '>=',
      '==',
      'and',
      'or',
      'not'
    ),

    term_parenthesized: $ => prec(PREC.PAREN, seq(
      '(',
      $.term,
      ')',
    )),

    pattern: $ => choice(
      $.pattern_default,
      $.pattern_var,
      $.pattern_constructor,
      $.pattern_tuple,
    ),

    pattern_default: $ => '_',

    pattern_var: $ => $.identifier,

    pattern_constructor: $ => seq(
      $.identifier,
      $.pattern,
    ),

    pattern_tuple: $ => seq(
      '{',
      $.pattern,
      repeat1(seq(',', $.pattern)),
      '}',
    ),

    identifier: $ => /[a-z][a-zA-Z0-9_']*/,
    Identifier: $ => /[A-Z][a-zA-Z0-9_']*/,
  },
});
