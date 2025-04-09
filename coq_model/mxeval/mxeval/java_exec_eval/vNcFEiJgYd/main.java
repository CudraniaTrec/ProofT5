import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class SquareNums {
    public static List<Integer> squareNums(List<Integer> nums) {
        List<Integer> res = new ArrayList<>();
        for ( int i = 0;i < nums.size(); i++ ) {
            res.add(nums.get(i) * nums.get(i));
        }
        return res;
    }
}


class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        List<Integer> arg00 = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        List<Integer> x0 = SquareNums.squareNums(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10));
        List<Integer> v0 = Arrays.asList(1, 4, 9, 16, 25, 36, 49, 64, 81, 100);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(10, 20, 30);
        List<Integer> x1 = SquareNums.squareNums(Arrays.asList(10, 20, 30));
        List<Integer> v1 = Arrays.asList(100, 400, 900);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(12, 15);
        List<Integer> x2 = SquareNums.squareNums(Arrays.asList(12, 15));
        List<Integer> v2 = Arrays.asList(144, 225);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
